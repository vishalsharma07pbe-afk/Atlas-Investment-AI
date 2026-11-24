package com.trading.api;

import java.util.*;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

/** Local service selection only. Never returns holding IDs, balances, owner IDs or costs. */
@RestController
@RequestMapping("/api/v1/internal/feed")
public class InternalPortfolioResearchController {
 private final JdbcTemplate jdbc;
 private final InternalFeedController authorization;
 public InternalPortfolioResearchController(JdbcTemplate jdbc,InternalFeedController authorization){
  this.jdbc=jdbc;this.authorization=authorization;
 }
 @GetMapping("/portfolio-research-identities")
 public List<Map<String,Object>> identities(HttpServletRequest request){
  authorization.requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
  // Resolve held symbols with the same ambiguity rule as Portfolio Doctor.
  return jdbc.queryForList("""
    WITH held AS (SELECT DISTINCT upper(symbol) symbol FROM personal_holdings WHERE asset_type='EQUITY'),
    resolved AS (
      SELECT h.symbol,i.isin,e.code AS exchange,i.id,
        count(*) OVER(PARTITION BY h.symbol) matches,
        count(i.isin) OVER(PARTITION BY h.symbol) known_isins,
        min(i.isin) OVER(PARTITION BY h.symbol) min_isin,
        max(i.isin) OVER(PARTITION BY h.symbol) max_isin,
        row_number() OVER(PARTITION BY h.symbol ORDER BY CASE WHEN e.code='NSE' THEN 0 ELSE 1 END,i.id) priority
      FROM held h JOIN instruments i ON upper(i.symbol)=h.symbol JOIN exchanges e ON e.id=i.exchange_id
      WHERE i.active AND i.series='EQ' AND i.listing_status='ACTIVE'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK') AND e.code IN ('NSE','BSE')
    )
    SELECT DISTINCT isin,exchange FROM resolved
    WHERE priority=1 AND isin ~ '^IN[A-Z0-9]{10}$'
      AND (matches=1 OR (matches=known_isins AND min_isin=max_isin))
    ORDER BY isin,exchange LIMIT 200
    """);
 }
}
