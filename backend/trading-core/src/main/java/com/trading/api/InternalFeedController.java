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
  @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean capUsageRights;

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
             to_char(i.listed_on,'YYYY-MM-DD') AS listed_on,to_char(i.delisted_on,'YYYY-MM-DD') AS delisted_on,
             i.source AS registry_source,i.source_revision AS registry_revision,
             count(*) OVER () AS recent_registry_count,calendar.expected_session,
             count(*) FILTER (WHERE (latest.candle_time AT TIME ZONE e.timezone)::date=calendar.expected_session) OVER () AS expected_session_count,
             (SELECT max(a.ex_date) FROM corporate_actions a
               WHERE a.instrument_id=i.id
               AND a.ex_date <= (latest.candle_time AT TIME ZONE e.timezone)::date) AS latest_action_date,
             coalesce((SELECT jsonb_agg(jsonb_build_object('action_type',a.action_type,'ex_date',a.ex_date,
                 'ratio',a.ratio::text,'cash_amount',a.cash_amount::text,'ratio_basis',a.raw_payload->>'ratio_basis',
                 'isin',a.raw_payload->>'isin','source_revision',a.source_revision))
               FROM (SELECT ca.action_type,ca.ex_date,ca.ratio,ca.cash_amount,ca.raw_payload,ca.source_revision
                 FROM corporate_actions ca WHERE ca.instrument_id=i.id
                   AND ca.ex_date <= (latest.candle_time AT TIME ZONE e.timezone)::date
                 ORDER BY ca.ex_date DESC,ca.action_type,ca.source_revision LIMIT 33) a),'[]'::jsonb)::text AS corporate_action_context
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
      ORDER BY CASE WHEN calendar.expected_session IS NOT NULL AND
        (latest.candle_time AT TIME ZONE e.timezone)::date=calendar.expected_session THEN 0 ELSE 1 END,
        latest.close*latest.volume DESC NULLS LAST,i.id LIMIT 200
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

  /** Atomic replacement of a dated public classification list, no account data. */
  @PostMapping("/amfi-equity-caps")
  @org.springframework.transaction.annotation.Transactional
  public Map<String,Object> amfiEquityCaps(HttpServletRequest request,@RequestBody com.fasterxml.jackson.databind.JsonNode body) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    if(!capUsageRights)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Market data rights required");
    java.time.LocalDate asOf;
    try{asOf=java.time.LocalDate.parse(body.path("as_of").asText());}
    catch(RuntimeException ex){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid cap period");}
    java.time.LocalDate today=java.time.LocalDate.now(MarketCalendarService.IST);
    if(!asOf.isBefore(today)||asOf.isBefore(today.minusDays(220))||
       !((asOf.getMonthValue()==6&&asOf.getDayOfMonth()==30)||(asOf.getMonthValue()==12&&asOf.getDayOfMonth()==31)))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid cap period");
    var items=body.path("items");
    if(!items.isArray()||items.size()<250||items.size()>10000)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid cap coverage");
    Set<String> seen=new HashSet<>();
    int large=0,mid=0;
    List<Object[]> values=new ArrayList<>();
    for(var item:items){
      String isin=item.path("isin").asText(""),category=item.path("category").asText("");
      var cap=item.path("average_cap_cr");
      if(!isin.matches("IN[A-Z0-9]{9}[0-9]")||!seen.add(isin)||!Set.of("LARGE_CAP","MID_CAP","SMALL_CAP").contains(category)||
         !cap.isNumber()||cap.decimalValue().signum()<=0||cap.decimalValue().compareTo(new java.math.BigDecimal("100000000"))>=0)
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid cap record");
      if(category.equals("LARGE_CAP"))large++;
      if(category.equals("MID_CAP"))mid++;
      values.add(new Object[]{isin,category,cap.decimalValue(),asOf});
    }
    if(large!=100||mid!=150)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Incomplete cap categories");
    jdbc.execute("LOCK TABLE discovery_amfi_cap IN EXCLUSIVE MODE");
    if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM discovery_amfi_cap WHERE as_of>?)",Boolean.class,asOf)))
      throw new ResponseStatusException(HttpStatus.CONFLICT,"Newer cap evidence already stored");
    jdbc.update("DELETE FROM discovery_amfi_cap");
    jdbc.batchUpdate("INSERT INTO discovery_amfi_cap(isin,category,average_cap_cr,as_of) VALUES (?,?,?,?)",values);
    return Map.of("as_of",asOf.toString(),"count",values.size());
  }

  private void requireExchange(String exchange) {
    if(!Set.of("NSE","BSE").contains(exchange))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Unsupported exchange");
  }

  /** Fixed public price-index history; no holdings, arbitrary instrument or provider calls. */
  @GetMapping("/strategy-benchmark")
  public Map<String,Object> strategyBenchmark(HttpServletRequest request) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    var rows=jdbc.queryForList("""
      WITH candidate AS (
        SELECT i.id,i.exchange_id FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
        WHERE e.code='NSE' AND i.active AND i.listing_status='ACTIVE'
          AND i.instrument_type='INDEX' AND i.exchange_token='NSE_INDEX|Nifty 50'
      )
      SELECT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date AS trade_date,
        c.open,c.close,c.revision,ds.source_code
      FROM candidate i JOIN market_candles c ON c.instrument_id=i.id
      JOIN data_sources ds ON ds.id=c.source_id
      WHERE (SELECT count(*) FROM candidate)=1 AND c.timeframe='1d' AND c.is_complete
        AND c.quality_status='PROVIDER_VALIDATED' AND c.adjustment_status='RAW_UNADJUSTED'
        AND ds.enabled AND ds.source_code='UPSTOX'
        AND c.candle_time < (now() AT TIME ZONE 'Asia/Kolkata')::date::timestamp AT TIME ZONE 'Asia/Kolkata'
        AND c.candle_time >= ((now() AT TIME ZONE 'Asia/Kolkata')::date-400)::timestamp AT TIME ZONE 'Asia/Kolkata'
        AND EXISTS(SELECT 1 FROM market_sessions s WHERE s.exchange_id=i.exchange_id
          AND s.session_date=(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date
          AND s.session_type='REGULAR' AND s.is_trading_day AND s.close_time=c.candle_time
          AND s.open_time IS NOT NULL AND s.open_time<s.close_time)
        AND NOT EXISTS(SELECT 1 FROM market_sessions s WHERE s.exchange_id=i.exchange_id
          AND s.session_date=(c.candle_time AT TIME ZONE 'Asia/Kolkata')::date
          AND s.is_trading_day AND s.session_type<>'REGULAR')
      ORDER BY c.candle_time LIMIT 400
      """);
    return Map.of("benchmark_key","NSE_INDEX|Nifty 50","kind","PRICE_INDEX","candles",rows);
  }

  /** Fixed bounded public historical calendar read. */
  @GetMapping("/strategy-calendar")
  public Map<String,Object> strategyCalendar(HttpServletRequest request,@RequestParam String exchange) {
    requireServiceToken(request.getHeader("X-Atlas-Service-Token"));
    requireExchange(exchange);
    return new MarketCalendarService(jdbc).historicalContext(exchange,java.time.LocalDate.now(MarketCalendarService.IST));
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
