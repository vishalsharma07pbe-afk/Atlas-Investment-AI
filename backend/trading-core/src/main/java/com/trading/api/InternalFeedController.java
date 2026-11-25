package com.trading.api;

import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.time.Instant;
import com.trading.market.MarketCalendarService;
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

  /** Public instrument identities with recent completed daily evidence; no holdings. */
  @GetMapping("/discovery-universe")
  public List<Map<String,Object>> discoveryUniverse(HttpServletRequest request,@RequestParam String exchange) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    requireExchange(exchange);
    return jdbc.queryForList("""
      WITH days AS (
        SELECT (now() AT TIME ZONE 'Asia/Kolkata')::date-g.n AS day
        FROM generate_series(1,14) AS g(n)
      ), calendar_days AS (
        SELECT d.day,CASE
          WHEN extract(isodow FROM d.day) IN (6,7) OR h.holiday_date IS NOT NULL THEN 'CLOSED'
          WHEN s.is_trading_day IS TRUE THEN 'TRADING'
          WHEN s.is_trading_day IS FALSE THEN 'CLOSED'
          ELSE 'UNKNOWN' END AS state
        FROM days d JOIN exchanges ex ON ex.code=?
        LEFT JOIN exchange_holidays h ON h.exchange_code=ex.code AND h.holiday_date=d.day
        LEFT JOIN market_sessions s ON s.exchange_id=ex.id AND s.session_date=d.day AND s.session_type='REGULAR'
      ), calendar AS (
        SELECT CASE WHEN max(day) FILTER (WHERE state='TRADING') >
           coalesce(max(day) FILTER (WHERE state='UNKNOWN'),DATE '1900-01-01')
          THEN max(day) FILTER (WHERE state='TRADING') END AS expected_session
        FROM calendar_days
      )
      SELECT i.id,e.code AS exchange,i.symbol,i.series,i.isin,i.instrument_type,i.listing_status,i.active,
             count(*) OVER () AS recent_registry_count,calendar.expected_session,
             (SELECT max(a.ex_date) FROM corporate_actions a
               WHERE a.instrument_id=i.id AND a.action_type IN ('SPLIT','BONUS','DIVIDEND')
               AND a.ex_date <= (latest.candle_time AT TIME ZONE e.timezone)::date) AS latest_action_date
      FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      JOIN LATERAL (
        SELECT c.close,c.volume,c.candle_time FROM market_candles c
        WHERE c.instrument_id=i.id AND c.timeframe='1d' AND c.is_complete
          AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
          AND c.candle_time < (now() AT TIME ZONE 'Asia/Kolkata')::date::timestamp AT TIME ZONE 'Asia/Kolkata'
          AND c.candle_time >= ((now() AT TIME ZONE 'Asia/Kolkata')::date-4)::timestamp AT TIME ZONE 'Asia/Kolkata'
        ORDER BY c.candle_time DESC LIMIT 1
      ) latest ON true
      CROSS JOIN calendar
      WHERE e.code=? AND i.active AND i.listing_status='ACTIVE' AND i.series='EQ'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK')
      ORDER BY latest.close*latest.volume DESC NULLS LAST,i.id LIMIT 200
      """,exchange,exchange);
  }

  /** Batch reads the same validated history used by the existing single-instrument route. */
  @GetMapping("/discovery-candles")
  public List<Map<String,Object>> discoveryCandles(HttpServletRequest request,@RequestParam String exchange,
      @RequestParam List<Long> ids) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    requireExchange(exchange);
    if(ids==null||ids.isEmpty()||ids.size()>20||new HashSet<>(ids).size()!=ids.size()
        ||ids.stream().anyMatch(id->id==null||id<=0))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Expected 1-20 distinct positive instrument IDs");
    List<Object> args=new ArrayList<>();
    args.add(exchange);
    args.addAll(ids);
    // Only the placeholder count varies; all values remain bound SQL parameters.
    String placeholders=String.join(",",Collections.nCopies(ids.size(),"?"));
    return jdbc.queryForList("""
      SELECT i.id AS instrument_id,c.* FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      CROSS JOIN LATERAL (
        SELECT (b.candle_time AT TIME ZONE e.timezone)::date trade_date,b.open,b.high,b.low,b.close,b.volume,
          b.adjustment_status,b.revision,b.quality_status,ds.source_code
        FROM market_candles b LEFT JOIN data_sources ds ON ds.id=b.source_id
        WHERE b.instrument_id=i.id AND b.timeframe='1d' AND b.is_complete
          AND b.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
          AND b.candle_time < (now() AT TIME ZONE 'Asia/Kolkata')::date::timestamp AT TIME ZONE 'Asia/Kolkata'
        ORDER BY b.candle_time DESC LIMIT 250
      ) c
      WHERE e.code=? AND i.active AND i.listing_status='ACTIVE' AND i.series='EQ'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK') AND i.id IN (
      """+placeholders+") ORDER BY i.id,c.trade_date",args.toArray());
  }

  private void requireExchange(String exchange) {
    if(!Set.of("NSE","BSE").contains(exchange))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Unsupported exchange");
  }

  @GetMapping("/session-context")
  public Map<String,Object> sessionContext(HttpServletRequest request) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    Instant instant=Instant.now();
    var calendar=new MarketCalendarService(jdbc);
    return Map.of("observed_at",instant.toString(),"timezone","Asia/Kolkata",
      "sessions",List.of(calendar.sessionContext("NSE",instant),calendar.sessionContext("BSE",instant)));
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
