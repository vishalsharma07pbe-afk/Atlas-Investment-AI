package com.trading.market;

import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Bounded, permission-gated backfill for the shared local research universe.
 * Uses the already configured operator market-data token, never an arbitrary
 * user's vault credential. Existing portfolio refresh remains independent.
 */
@Service
public class DiscoveryHistoryScheduler {
  // Align ingestion with all existing daily research horizons (long term: 200 sessions).
  private static final int REQUIRED_DAILY_CANDLES=200;
  private static final int BACKFILL_MONTHS=12;
  private final JdbcTemplate jdbc;
  private final UpstoxFeedService stocks;
  private final MarketCalendarService calendar;
  @Value("${ATLAS_DISCOVERY_HISTORY_ENABLED:false}") boolean enabled;
  @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean usageRights;
  @Value("${MARKET_DATA_ENTITLEMENT_CONFIRMED:false}") boolean entitlement;
  @Value("${UPSTOX_ACCESS_TOKEN:}") String accessToken="";
  public DiscoveryHistoryScheduler(JdbcTemplate jdbc,UpstoxFeedService stocks,MarketCalendarService calendar){
    this.jdbc=jdbc;this.stocks=stocks;this.calendar=calendar;
  }

  @Scheduled(initialDelayString="${atlas.discovery.history.initial-ms:60000}",
             fixedDelayString="${atlas.discovery.history.poll-ms:300000}")
  public void scheduled(){
    if(!enabled||!usageRights||!entitlement||accessToken.isBlank())return;
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    // Two requests per exchange per pass at most. No current-day bars.
    for(String exchange:List.of("NSE","BSE")){
      LocalDate end;
      try{end=calendar.lastTradingDay(exchange,today);}catch(IllegalStateException ex){continue;}
      refreshExchange(exchange,end);
    }
  }

  void refreshExchange(String exchange,LocalDate end){
    if(!Set.of("NSE","BSE").contains(exchange))throw new IllegalArgumentException("exchange");
    // Keep only active cash equities with explicit mappings. Skip adjusted
    // series rather than create a mixed adjustment history.
    var rows=jdbc.queryForList("""
      SELECT i.id,m.instrument_key,h.candle_count,h.latest_date
      FROM instruments i JOIN exchanges e ON e.id=i.exchange_id
      JOIN LATERAL (
        SELECT instrument_key FROM upstox_instrument_map
        WHERE exchange_code=e.code AND trading_symbol=i.symbol AND isin=i.isin
          AND isin ~ '^IN[A-Z0-9]{10}$'
          AND instrument_key LIKE e.code||'_EQ|%'
          AND instrument_type IN ('EQ','EQUITY')
        ORDER BY instrument_key LIMIT 1
      ) m ON true
      LEFT JOIN discovery_history_attempts a ON a.instrument_id=i.id
      CROSS JOIN LATERAL (
        SELECT count(*) candle_count,max((c.candle_time AT TIME ZONE 'Asia/Kolkata')::date) latest_date,
               bool_or(c.adjustment_status='ADJUSTED') has_adjusted
        FROM market_candles c WHERE c.instrument_id=i.id AND c.timeframe='1d'
          AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
      ) h
      WHERE e.code=? AND i.active AND i.listing_status='ACTIVE' AND i.series='EQ'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK')
        AND NOT coalesce(h.has_adjusted,false)
        AND (h.candle_count<? OR h.latest_date IS NULL OR h.latest_date<?)
        AND (a.next_attempt_at IS NULL OR a.next_attempt_at<=now())
      ORDER BY a.attempted_at ASC NULLS FIRST,i.id
      LIMIT 2
      """,exchange,REQUIRED_DAILY_CANDLES,end);
    for(var row:rows){
      long id=((Number)row.get("id")).longValue();
      long count=((Number)row.get("candle_count")).longValue();
      Object raw=row.get("latest_date");
      LocalDate latest=raw instanceof java.sql.Date d?d.toLocalDate():raw instanceof LocalDate d?d:null;
      // Claim before network I/O; a restart or duplicate invocation cannot
      // repeatedly fetch the same instrument in a tight loop.
      int claimed=jdbc.update("""
        INSERT INTO discovery_history_attempts(instrument_id,attempted_at,next_attempt_at,status)
        VALUES (?,now(),now()+interval '6 hours','RUNNING')
        ON CONFLICT(instrument_id) DO UPDATE SET attempted_at=now(),
          next_attempt_at=now()+interval '6 hours',status='RUNNING'
        WHERE discovery_history_attempts.next_attempt_at<=now()
        """,id);
      if(claimed==0)continue;
      try{
        LocalDate floor=end.minusMonths(BACKFILL_MONTHS);
        LocalDate from=count<REQUIRED_DAILY_CANDLES||latest==null||latest.isBefore(floor)?floor:latest.plusDays(1);
        if(from.isAfter(end))from=floor;
        int written=stocks.discoveryDailyCandles(accessToken,(String)row.get("instrument_key"),from,end);
        jdbc.update("UPDATE discovery_history_attempts SET status='SUCCESS',rows_written=?,next_attempt_at=now()+interval '1 day' WHERE instrument_id=?",written,id);
      }catch(Exception ex){
        // Never store provider response bodies, URLs or credentials.
        jdbc.update("UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,next_attempt_at=now()+interval '6 hours' WHERE instrument_id=?",id);
      }
    }
  }
}
