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
    return digest+ownershipChanges()+thesisChanges()+portfolioLevelRisk();
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

  /** Only the lifecycle monitors' current visible changes are eligible.
   * One event per holding identity, metric and reported period, not per poll.
   */
  private int thesisChanges(){
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
      ), holdings AS (
        SELECT f.user_id,f.generated_at,item
        FROM fresh f CROSS JOIN LATERAL jsonb_array_elements(
          CASE WHEN jsonb_typeof(f.result->'holdings')='array' THEN f.result->'holdings' ELSE '[]'::jsonb END
        ) item
        WHERE item->>'id' ~ '^[0-9]+$' AND length(item->>'symbol') BETWEEN 1 AND 120
      ), financial AS (
        SELECT h.user_id,h.generated_at,item->>'id' AS holding_id,item->>'symbol' AS symbol,
          (item->>'exchange')||':'||(item->>'isin') AS identity,
          change->>'metric' AS metric,change->>'current_period' AS period,
          'FINANCIAL_DIRECTION' AS kind,
          change->>'current_direction' AS direction
        FROM holdings h CROSS JOIN LATERAL jsonb_array_elements(
          CASE WHEN jsonb_typeof(item->'thesis_changes')='array' THEN item->'thesis_changes' ELSE '[]'::jsonb END
        ) change
        WHERE item->>'asset_type'='EQUITY'
          AND item->>'exchange' IN ('NSE','BSE') AND item->>'isin' ~ '^IN[A-Z0-9]{10}$'
          AND change->>'metric' IN ('REVENUE','NET_PROFIT','OPERATING_PROFIT','OPERATING_CASH_FLOW')
          AND change->>'current_direction' IN ('NEGATIVE','DECLINING')
          AND change->>'previous_direction' IN ('NEGATIVE','DECLINING','IMPROVING','UNCHANGED')
          AND change->>'previous_direction'<>change->>'current_direction'
          AND length(change->>'current_period') BETWEEN 1 AND 80
          AND length(change->>'previous_period') BETWEEN 1 AND 80
          AND change->>'current_period'<>change->>'previous_period'
      ), funds AS (
        SELECT h.user_id,h.generated_at,item->>'id' AS holding_id,item->>'symbol' AS symbol,
          item->>'fund_monitor_identity' AS identity,
          change->>'metric' AS metric,change->>'currentDate' AS period,
          'FUND_DISCLOSURE' AS kind,'REVIEW' AS direction
        FROM holdings h CROSS JOIN LATERAL jsonb_array_elements(
          CASE WHEN jsonb_typeof(item->'fund_thesis_changes')='array' THEN item->'fund_thesis_changes' ELSE '[]'::jsonb END
        ) change
        WHERE item->>'asset_type'='MUTUAL_FUND'
          AND item->>'exact_scheme_code' ~ '^[1-9][0-9]{5,8}$'
          AND item->>'fund_monitor_identity' ~ '^[1-9][0-9]{5,8}:IN[A-Z0-9]{10}:(DIRECT|REGULAR):TIGZIG_AMFI_DERIVED$'
          AND split_part(item->>'fund_monitor_identity',':',1)=item->>'exact_scheme_code'
          AND change->>'metric' IN ('TER','RISKOMETER','BENCHMARK','MANAGERS','EXIT_LOAD')
          AND change->>'attention'='REVIEW'
          AND change->>'currentDate' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
          AND change->>'previousDate' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
          AND change->>'currentDate'>change->>'previousDate'
      ), events AS (
        SELECT * FROM financial UNION ALL SELECT * FROM funds
      )
      INSERT INTO user_notification_history(user_id,event_type,title,message,source_code,
        source_reference,occurred_at,details,dedupe_key,delivery_channel,delivery_status)
      SELECT user_id,'PORTFOLIO_RISK',
        CASE kind WHEN 'FINANCIAL_DIRECTION' THEN 'Financial thesis review' ELSE 'Fund disclosure review' END,
        CASE kind WHEN 'FINANCIAL_DIRECTION' THEN
          symbol||': reported '||replace(lower(metric),'_',' ')||' direction is '||lower(direction)||
          ' for '||period||'. Review dated financial evidence and verify official filings.'
        ELSE symbol||': reported '||replace(lower(metric),'_',' ')||' change dated '||period||
          ' needs review. Secondary evidence; verify official disclosure.' END,
        'ATLAS_PORTFOLIO_REVIEW',holding_id||':'||metric||':'||period,generated_at,
        jsonb_build_object('holding_id',holding_id,'metric',metric,'period',period,'kind',kind,'direction',direction),
        'portfolio-thesis:'||md5(jsonb_build_array(holding_id,identity,kind,metric,period)::text),
        'IN_APP','DELIVERED'
      FROM events
      ON CONFLICT DO NOTHING
      """);
  }

  /** Separate weekly cooldown per risk family; no alerts from incomplete evidence. */
  private int portfolioLevelRisk(){
    return jdbc.update("""
      WITH fresh AS (
        SELECT s.user_id,s.generated_at,s.result,
          date_trunc('week',now() AT TIME ZONE 'Asia/Kolkata')::date AS week_start
        FROM portfolio_review_snapshots s
        WHERE s.generated_at BETWEEN now()-interval '5 minutes' AND now()
          AND s.holdings_revision=(
            SELECT md5(coalesce(string_agg(h.id::text||':'||h.updated_at::text,',' ORDER BY h.id),''))
            FROM personal_holdings h WHERE h.user_id=s.user_id
          )
          AND s.result->>'methodology'='PORTFOLIO_REVIEW_V1'
      ), flags AS (
        SELECT f.user_id,f.generated_at,f.week_start,flag,
          CASE WHEN flag->>'kind'='BENCHMARK_RELATIVE_LAG' THEN 'BENCHMARK' ELSE 'CONCENTRATION' END AS family
        FROM fresh f CROSS JOIN LATERAL jsonb_array_elements(
          CASE WHEN jsonb_typeof(f.result->'portfolio_level_risk'->'attention')='array'
            THEN f.result->'portfolio_level_risk'->'attention' ELSE '[]'::jsonb END
        ) flag
        WHERE flag->>'kind' IN ('BENCHMARK_RELATIVE_LAG','SINGLE_IDENTITY','TOP_THREE','DIRECT_EQUITY_SECTOR')
          AND length(flag->>'label') BETWEEN 1 AND 200 AND jsonb_typeof(flag->'value')='number'
          AND flag->>'evidenceThrough' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
          AND (
            (flag->>'kind'='BENCHMARK_RELATIVE_LAG'
              AND f.result->'portfolio_level_risk'->>'benchmark_status'='COMPARABLE_PRICE_REFERENCE'
              AND flag->>'unit'='PP')
            OR
            (flag->>'kind'<>'BENCHMARK_RELATIVE_LAG'
              AND f.result->'portfolio_level_risk'->>'concentration_status'='RECENT_RECORDED_EXPOSURES'
              AND flag->>'unit'='PERCENT'
              AND flag->>'evidenceThrough'=(now() AT TIME ZONE 'Asia/Kolkata')::date::text)
          )
      ), grouped AS (
        SELECT user_id,generated_at,week_start,family,
          jsonb_agg(flag ORDER BY flag->>'kind',flag->>'label') AS evidence,count(*) AS finding_count
        FROM flags GROUP BY user_id,generated_at,week_start,family
      )
      INSERT INTO user_notification_history(user_id,event_type,title,message,source_code,
        source_reference,occurred_at,details,dedupe_key,delivery_channel,delivery_status)
      SELECT user_id,'PORTFOLIO_RISK',
        CASE family WHEN 'BENCHMARK' THEN 'Benchmark underperformance review' ELSE 'Portfolio concentration review' END,
        CASE family WHEN 'BENCHMARK' THEN
          'Recorded 13-week portfolio return estimate lags the NIFTY 50 price reference by at least five percentage points. Not a personalized benchmark.'
        ELSE finding_count||' aggregate exposure observation(s) exceed review thresholds using recent recorded values. Fund look-through is excluded.' END
          ||' Open My Portfolio for the dated evidence; no trade recommendation.',
        'ATLAS_PORTFOLIO_REVIEW',family||':'||week_start::text,generated_at,
        jsonb_build_object('family',family,'week_start',week_start,'attention',evidence),
        'portfolio-level:'||family||':'||week_start::text,'IN_APP','DELIVERED'
      FROM grouped
      ON CONFLICT DO NOTHING
      """);
  }
}
