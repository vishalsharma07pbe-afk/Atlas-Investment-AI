package com.trading.market;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Records local holdings valuations, never broker executions or reconstructed history. */
@Service
public class PortfolioValuationHistoryService {
  private final JdbcTemplate jdbc;
  public PortfolioValuationHistoryService(JdbcTemplate jdbc){this.jdbc=jdbc;}

  /**
   * One bounded atomic statement, with one observation per owner/date.
   * A recent observation from today is required; no copying yesterday's
   * snapshot just because the application restarted. Existing snapshots win.
   * Prices can still have different observation dates and are not certified closes.
   */
  public int captureDue(int requestedLimit){
    int limit=Math.max(1,Math.min(5,requestedLimit));
    return jdbc.update("""
      WITH clock AS (
        SELECT (now() AT TIME ZONE 'Asia/Kolkata')::date AS today
      ), eligible AS (
        SELECT h.user_id,sum(h.quantity*h.last_price) AS total_value,
          count(*) AS priced_positions,min(h.price_as_of) AS oldest_price_at,
          max(h.price_as_of) AS newest_price_at,clock.today
        FROM personal_holdings h CROSS JOIN clock
        WHERE NOT EXISTS (
          SELECT 1 FROM portfolio_valuation_snapshots s
          WHERE s.user_id=h.user_id AND s.valuation_date=clock.today
        )
        GROUP BY h.user_id,clock.today
        HAVING bool_and(h.last_price IS NOT NULL AND h.last_price>=0
          AND h.price_as_of IS NOT NULL AND h.price_as_of<=now()
          AND clock.today-(h.price_as_of AT TIME ZONE 'Asia/Kolkata')::date
            <= CASE WHEN h.asset_type='MUTUAL_FUND' THEN 7 ELSE 5 END)
          AND (max(h.price_as_of) AT TIME ZONE 'Asia/Kolkata')::date=clock.today
        ORDER BY h.user_id LIMIT ?
      )
      INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,
        priced_positions,unpriced_positions,capture_source,oldest_price_at,newest_price_at)
      SELECT user_id,today,total_value,priced_positions,0,'AUTO_RECORDED',oldest_price_at,newest_price_at
      FROM eligible ON CONFLICT(user_id,valuation_date) DO NOTHING
      """,limit);
  }
}
