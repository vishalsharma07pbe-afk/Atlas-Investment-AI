package com.trading.market;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Local daily attention digest, using only current owner-scoped review snapshots.
 * Existing notification storage and read-state APIs remain authoritative.
 */
@Service
public class PortfolioRiskNotifications {
  private final JdbcTemplate jdbc;
  public PortfolioRiskNotifications(JdbcTemplate jdbc){this.jdbc=jdbc;}

  public int evaluate(){
    // One digest per owner per IST date, not one alert per finding or polling cycle.
    // The holdings revision check suppresses notifications from deleted/changed holdings.
    int digest=jdbc.update("""
      WITH fresh AS (
        SELECT s.user_id,s.generated_at,s.result,
          (now() AT TIME ZONE 'Asia/Kolkata')::date AS digest_date
        FROM portfolio_review_snapshots s
        WHERE s.generated_at BETWEEN now()-interval '5 minutes' AND now()
          AND s.holdings_revision=(
            SELECT md5(coalesce(string_agg(h.id::text||':'||h.updated_at::text,',' ORDER BY h.id),''))
            FROM personal_holdings h WHERE h.user_id=s.user_id
          )
          AND s.result->>'methodology'='PORTFOLIO_REVIEW_V1'
      ), attention AS (
        SELECT f.user_id,f.generated_at,f.digest_date,count(*) AS finding_count,
          string_agg(item->>'symbol',', ' ORDER BY item->>'symbol') AS symbols
        FROM fresh f CROSS JOIN LATERAL jsonb_array_elements(f.result->'holdings') item
        WHERE item->>'status'='REVIEW_REQUIRED'
        GROUP BY f.user_id,f.generated_at,f.digest_date
      )
      INSERT INTO user_notification_history(user_id,event_type,title,message,source_code,
        source_reference,occurred_at,details,dedupe_key,delivery_channel,delivery_status)
      SELECT user_id,'PORTFOLIO_RISK','Portfolio review needs attention',
        finding_count||' holding(s) have recorded risk observations: '||left(symbols,500)||
        '. Open My Portfolio for the evidence and limitations. Recorded values are not verified live prices.',
        'ATLAS_PORTFOLIO_REVIEW',digest_date::text,generated_at,
        jsonb_build_object('holding_count',finding_count,'review_generated_at',generated_at),
        'portfolio-review:'||digest_date::text,'IN_APP','DELIVERED'
      FROM attention
      ON CONFLICT DO NOTHING
      """);
    return digest+ownershipChanges();
  }

  private int ownershipChanges(){
    // A separate local event per holding/quarter, even if today's risk digest
    // has already been delivered. Only current matched review evidence is used.
    return jdbc.update("""
      WITH fresh AS (
        SELECT s.user_id,s.generated_at,s.result
        FROM portfolio_review_snapshots s
        WHERE s.generated_at BETWEEN now()-interval '5 minutes' AND now()
          AND s.holdings_revision=(
            SELECT md5(coalesce(string_agg(h.id::text||':'||h.updated_at::text,',' ORDER BY h.id),''))
            FROM personal_holdings h WHERE h.user_id=s.user_id
          )
          AND s.result->>'methodology'='PORTFOLIO_REVIEW_V1'
      ), changes AS (
        SELECT f.user_id,f.generated_at,item->>'id' AS holding_id,item->>'symbol' AS symbol,
          item->>'isin' AS isin,item->>'exchange' AS exchange,
          change->>'currentDate' AS quarter,
          string_agg(DISTINCT change->>'category',', ' ORDER BY change->>'category') AS categories
        FROM fresh f CROSS JOIN LATERAL jsonb_array_elements(f.result->'holdings') item
        CROSS JOIN LATERAL jsonb_array_elements(coalesce(item->'ownership_changes','[]'::jsonb)) change
        WHERE item->>'asset_type'='EQUITY' AND change->>'attention'='REVIEW'
          AND item->>'id' ~ '^[0-9]+$' AND item->>'isin' ~ '^IN[A-Z0-9]{10}$'
          AND item->>'exchange' IN ('NSE','BSE') AND change->>'currentDate' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
          AND change->>'category' IN ('promoters','fii','other_dii','mutual_funds')
        GROUP BY f.user_id,f.generated_at,item->>'id',item->>'symbol',item->>'isin',item->>'exchange',change->>'currentDate'
      )
      INSERT INTO user_notification_history(user_id,event_type,title,message,source_code,
        source_reference,occurred_at,details,dedupe_key,delivery_channel,delivery_status)
      SELECT user_id,'PORTFOLIO_RISK','Quarterly ownership review',
        left(symbol,120)||': reported ownership decline in '||categories||
        ' for quarter ending '||quarter||'. Verify filings and share counts; this is not proof of sales.',
        'ATLAS_PORTFOLIO_REVIEW',holding_id||':'||quarter,generated_at,
        jsonb_build_object('holding_id',holding_id,'quarter',quarter,'categories',categories),
        'portfolio-ownership:'||holding_id||':'||exchange||':'||isin||':'||quarter,'IN_APP','DELIVERED'
      FROM changes
      ON CONFLICT DO NOTHING
      """);
  }
}
