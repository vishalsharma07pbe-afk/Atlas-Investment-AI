package com.trading.api;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/instruments")
public class InstrumentController {
  private final JdbcTemplate jdbc;
  public InstrumentController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

  @GetMapping
  public List<Map<String,Object>> list(@RequestParam(defaultValue="50") int limit,
                                       @RequestParam(required=false) String q,
                                       @RequestParam(required=false) String exchange) {
    int safeLimit = Math.max(1, Math.min(limit, 200));
    if (q == null || q.isBlank()) {
      if (exchange == null || exchange.isBlank()) return jdbc.queryForList("SELECT i.id,e.code AS exchange,i.symbol,i.series,i.isin,i.security_name,i.instrument_type,i.listing_status,i.active,i.source,i.source_revision,i.updated_at " +
        "FROM instruments i JOIN exchanges e ON e.id=i.exchange_id ORDER BY e.code,i.symbol LIMIT ?", safeLimit);
      return jdbc.queryForList("SELECT i.id,e.code AS exchange,i.symbol,i.series,i.isin,i.security_name,i.instrument_type,i.listing_status,i.active,i.source,i.source_revision,i.updated_at " +
        "FROM instruments i JOIN exchanges e ON e.id=i.exchange_id WHERE e.code=? ORDER BY e.code,i.symbol LIMIT ?", exchange.trim().toUpperCase(),safeLimit);
    }
    String term=q.trim(), contains="%"+term+"%";
    String select="SELECT i.id,e.code AS exchange,i.symbol,i.series,i.isin,i.security_name,i.instrument_type,i.listing_status,i.active,i.source,i.source_revision,i.updated_at FROM instruments i JOIN exchanges e ON e.id=i.exchange_id ";
    if(exchange == null || exchange.isBlank()) return jdbc.queryForList(select +
      "WHERE (i.symbol ILIKE ? OR i.isin ILIKE ? OR i.security_name ILIKE ?) ORDER BY CASE WHEN i.symbol ILIKE ? THEN 0 ELSE 1 END,e.code,i.symbol LIMIT ?",
      contains,contains,contains,term+"%",safeLimit);
    return jdbc.queryForList(select +
      "WHERE (i.symbol ILIKE ? OR i.isin ILIKE ? OR i.security_name ILIKE ?) AND e.code=? ORDER BY CASE WHEN i.symbol ILIKE ? THEN 0 ELSE 1 END,e.code,i.symbol LIMIT ?",
      contains,contains,contains,exchange.trim().toUpperCase(),term+"%",safeLimit);
  }
}
