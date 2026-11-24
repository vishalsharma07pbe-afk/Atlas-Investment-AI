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
    return jdbc.update("""
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
  }
}
