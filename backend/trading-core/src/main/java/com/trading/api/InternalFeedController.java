package com.trading.api;

import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Minimal machine-to-machine portfolio selection for the read-only quote feed. */
@RestController
@RequestMapping("/api/v1/internal/feed")
public class InternalFeedController {
  private final JdbcTemplate jdbc;
  private final InstrumentController instruments;
  private final MarketDataController marketData;
  private final DataHealthController dataHealth;
  private final String serviceToken;

  public InternalFeedController(JdbcTemplate jdbc, InstrumentController instruments,
      MarketDataController marketData, DataHealthController dataHealth,
      @Value("${INTERNAL_SERVICE_TOKEN:}") String serviceToken) {
    this.jdbc=jdbc;
    this.instruments=instruments;
    this.marketData=marketData;
    this.dataHealth=dataHealth;
    this.serviceToken=serviceToken;
  }

  @GetMapping("/instruments")
  public List<Map<String,Object>> instruments(HttpServletRequest request,
      @RequestParam(defaultValue="50") int limit,
      @RequestParam(required=false) String q,
      @RequestParam(required=false) String exchange) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    return instruments.list(limit,q,exchange);
  }

  @GetMapping("/instruments/{id}")
  public ResponseEntity<Map<String,Object>> instrument(HttpServletRequest request,@PathVariable long id) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    return instruments.getById(id);
  }

  @GetMapping("/instruments/{id}/candles")
  public Map<String,Object> candles(HttpServletRequest request,@PathVariable long id,
      @RequestParam(defaultValue="500") int limit) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    return marketData.candles(id,limit);
  }

  @GetMapping("/data-health/summary")
  public Map<String,Object> dataHealth(HttpServletRequest request) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    return dataHealth.summary();
  }

  @GetMapping("/equity-subscriptions")
  public Map<String,Object> equitySubscriptions(HttpServletRequest request) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    List<String> symbols=jdbc.queryForList("""
      SELECT DISTINCT upper(symbol) FROM personal_holdings
      WHERE asset_type='EQUITY' ORDER BY upper(symbol)
      """,String.class);
    List<Map<String,Object>> resolved=jdbc.queryForList("""
      WITH held AS (
        SELECT DISTINCT upper(symbol) symbol FROM personal_holdings WHERE asset_type='EQUITY'
      ), ranked AS (
        SELECT h.symbol,m.instrument_key,m.exchange_code,m.instrument_type,
          row_number() OVER (PARTITION BY h.symbol ORDER BY
            CASE WHEN m.exchange_code='NSE' THEN 0 ELSE 1 END,
            CASE WHEN m.instrument_type='EQ' THEN 0 ELSE 1 END,
            m.instrument_key) priority
        FROM held h JOIN upstox_instrument_map m ON upper(m.trading_symbol)=h.symbol
        WHERE m.instrument_key LIKE 'NSE_EQ|%' OR m.instrument_key LIKE 'BSE_EQ|%'
      )
      SELECT symbol,instrument_key,exchange_code,instrument_type FROM ranked
      WHERE priority=1 ORDER BY symbol
      """);
    Set<String> found=new HashSet<>();
    for(Map<String,Object> row:resolved)found.add(String.valueOf(row.get("symbol")));
    List<String> missing=symbols.stream().filter(symbol->!found.contains(symbol)).toList();
    return Map.of(
      "selection_mode","PORTFOLIO_AUTOMATIC",
      "holding_symbol_count",symbols.size(),
      "resolved_count",resolved.size(),
      "subscriptions",resolved,
      "missing_symbols",missing
    );
  }

  void requireServiceToken(String received) {
    if(serviceToken==null || serviceToken.isBlank() || received==null ||
       !MessageDigest.isEqual(serviceToken.getBytes(StandardCharsets.UTF_8),
                              received.getBytes(StandardCharsets.UTF_8)))
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,"Invalid internal service credential");
  }
}
