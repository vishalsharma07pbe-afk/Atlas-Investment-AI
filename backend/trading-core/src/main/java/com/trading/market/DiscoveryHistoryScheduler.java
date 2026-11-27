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
  @Value("${ATLAS_DISCOVERY_QUOTE_SCREEN_ENABLED:false}") boolean quoteScreenEnabled;
  @Value("${atlas.discovery.history.request-gap-ms:1000}") long requestGapMs;
  public DiscoveryHistoryScheduler(JdbcTemplate jdbc,UpstoxFeedService stocks,MarketCalendarService calendar){
    this.jdbc=jdbc;this.stocks=stocks;this.calendar=calendar;
  }

  @Scheduled(initialDelayString="${atlas.discovery.history.initial-ms:60000}",
             fixedDelayString="${atlas.discovery.history.poll-ms:120000}")
  public void scheduled(){
    if(!enabled||!usageRights||!entitlement||accessToken.isBlank())return;
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    // Up to ten requests per venue; adaptive allocation reserves six maintenance
    // and four expansion slots when both pools are due, and borrows unused slots.
    // Oldest eligible work in each pool is protected from priority starvation.
    // Sequential, paced REST calls; shared operator cooldown remains authoritative.
    for(String exchange:List.of("NSE","BSE")){
      LocalDate end;
      try{end=calendar.lastTradingDay(exchange,today);}catch(IllegalStateException ex){continue;}
      if(end.isBefore(today.minusDays(7)))continue;
      refreshExchange(exchange,end);
    }
  }

  private static LocalDate localDate(Object raw){
    return raw instanceof java.sql.Date d?d.toLocalDate():raw instanceof LocalDate d?d:null;
  }

  void refreshExchange(String exchange,LocalDate end){
    if(!Set.of("NSE","BSE").contains(exchange))throw new IllegalArgumentException("exchange");
    if(OperatorFeedCooldown.blocked(jdbc))return;
    // Keep only active cash equities with explicit mappings. Skip adjusted
    // series rather than create a mixed adjustment history.
    var rows=jdbc.queryForList("""
      WITH expected AS (
        SELECT s.exchange_id,s.session_date
        FROM market_sessions s JOIN exchanges ex ON ex.id=s.exchange_id
        WHERE ex.code=? AND s.session_date BETWEEN ? AND ?
          AND s.session_type='REGULAR' AND s.is_trading_day
          AND extract(isodow FROM s.session_date) BETWEEN 1 AND 5
          AND s.open_time IS NOT NULL AND s.close_time IS NOT NULL AND s.open_time<s.close_time
          AND (s.open_time AT TIME ZONE 'Asia/Kolkata')::date=s.session_date
          AND (s.close_time AT TIME ZONE 'Asia/Kolkata')::date=s.session_date
          AND NOT EXISTS(SELECT 1 FROM exchange_holidays h WHERE h.exchange_code=ex.code AND h.holiday_date=s.session_date)
          AND NOT EXISTS(SELECT 1 FROM market_sessions x WHERE x.exchange_id=s.exchange_id
            AND x.session_date=s.session_date AND x.is_trading_day AND x.session_type<>'REGULAR')
      ), candidates AS (
      SELECT i.id,m.instrument_key,h.candle_count,h.latest_date,g.first_missing_date,a.attempted_at,
        coalesce(candidate.priority,0) AS quote_priority,
        CASE WHEN h.candle_count>=25 AND h.latest_date<? THEN 0 ELSE 1 END AS workload
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
      LEFT JOIN discovery_security_context quality ON quality.instrument_id=i.id AND quality.instrument_key=m.instrument_key AND quality.isin=i.isin
      LEFT JOIN discovery_candidate_queue candidate ON candidate.instrument_id=i.id AND candidate.instrument_key=m.instrument_key AND candidate.isin=i.isin
      CROSS JOIN LATERAL (
        SELECT count(DISTINCT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date)
                 FILTER (WHERE c.candle_time >= ?::date::timestamp AT TIME ZONE 'Asia/Kolkata'
                   AND c.candle_time < (?::date+1)::timestamp AT TIME ZONE 'Asia/Kolkata') candle_count,
               max((c.candle_time AT TIME ZONE 'Asia/Kolkata')::date)
                 FILTER (WHERE c.candle_time < (?::date+1)::timestamp AT TIME ZONE 'Asia/Kolkata') latest_date,
               min((c.candle_time AT TIME ZONE 'Asia/Kolkata')::date) first_date,
               bool_or(c.adjustment_status='ADJUSTED') has_adjusted
        FROM market_candles c WHERE c.instrument_id=i.id AND c.timeframe='1d'
          AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
      ) h
      LEFT JOIN LATERAL (
        SELECT min(s.session_date) first_missing_date
        FROM expected s WHERE s.exchange_id=i.exchange_id AND s.session_date>=h.first_date
          AND (i.listed_on IS NULL OR s.session_date>=i.listed_on)
          AND (i.delisted_on IS NULL OR s.session_date<i.delisted_on)
          AND NOT EXISTS(
            SELECT 1 FROM market_candles c WHERE c.instrument_id=i.id AND c.timeframe='1d'
              AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
              AND c.candle_time>=s.session_date::timestamp AT TIME ZONE 'Asia/Kolkata'
              AND c.candle_time<(s.session_date+1)::timestamp AT TIME ZONE 'Asia/Kolkata')
      ) g ON true
      WHERE e.code=? AND i.active AND i.listing_status='ACTIVE' AND i.series='EQ'
        AND i.instrument_type IN ('EQ','EQUITY','STOCK')
        AND coalesce(quality.security_state,'UNKNOWN')<>'SUSPENDED_REPORTED'
        AND NOT coalesce(h.has_adjusted,false)
        AND (h.candle_count<? OR h.latest_date IS NULL OR h.latest_date<? OR g.first_missing_date IS NOT NULL)
        AND (a.next_attempt_at IS NULL OR a.next_attempt_at<=now())
      ), oldest AS (
        SELECT *,row_number() OVER (PARTITION BY workload ORDER BY attempted_at ASC NULLS FIRST,candle_count DESC,id) AS oldest_position
        FROM candidates
      ), ranked AS (
        SELECT *,row_number() OVER (PARTITION BY workload ORDER BY
          CASE WHEN oldest_position=1 THEN 10 ELSE quote_priority END DESC,attempted_at ASC NULLS FIRST,
          candle_count DESC,id) AS position
        FROM oldest
      )
      SELECT id,instrument_key,candle_count,latest_date,first_missing_date FROM ranked
      """.replace("CASE WHEN oldest_position=1 THEN 10 ELSE quote_priority END DESC,",quoteScreenEnabled?"CASE WHEN oldest_position=1 THEN 10 ELSE quote_priority END DESC,":"")+(quoteScreenEnabled?"""
      ORDER BY CASE WHEN workload=1 AND position=1 THEN 0
                    WHEN workload=0 AND position<=6 THEN 1
                    WHEN workload=1 AND position<=4 THEN 2 ELSE 3 END,
        workload,position LIMIT 10
      """:"""
      WHERE (workload=0 AND position<=8) OR (workload=1 AND position<=2)
      ORDER BY workload,position LIMIT 10
      """),exchange,end.minusMonths(BACKFILL_MONTHS),end,end,end.minusMonths(BACKFILL_MONTHS),end,end,exchange,REQUIRED_DAILY_CANDLES,end);
    for(var row:rows){
      if(OperatorFeedCooldown.blocked(jdbc))return;
      long id=((Number)row.get("id")).longValue();
      long count=((Number)row.get("candle_count")).longValue();
      LocalDate latest=localDate(row.get("latest_date"));
      LocalDate missing=localDate(row.get("first_missing_date"));
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
        // Pace even incremental requests; cancellation must not launch another provider call.
        if(requestGapMs>0)Thread.sleep(Math.max(1000,requestGapMs));
        if(OperatorFeedCooldown.blocked(jdbc)){
          jdbc.update("UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,next_attempt_at=now()+interval '15 minutes' WHERE instrument_id=?",id);
          return;
        }
        LocalDate floor=end.minusMonths(BACKFILL_MONTHS);
        LocalDate from=count<REQUIRED_DAILY_CANDLES||latest==null||latest.isBefore(floor)?floor:latest.plusDays(1);
        // Repair an interior known-session hole even if the latest candle is current.
        if(missing!=null&&!missing.isBefore(floor)&&!missing.isAfter(end)&&missing.isBefore(from))from=missing;
        if(from.isAfter(end))from=floor;
        int written=stocks.discoveryDailyCandles(accessToken,(String)row.get("instrument_key"),from,end);
        if(written>0){
          jdbc.update("UPDATE discovery_history_attempts SET status='SUCCESS',rows_written=?,next_attempt_at=now()+interval '12 hours' WHERE instrument_id=?",written,id);
          OperatorFeedCooldown.recovered(jdbc);
        }else
          jdbc.update("UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,next_attempt_at=now()+interval '6 hours' WHERE instrument_id=?",id);
      }catch(InterruptedException ex){
        Thread.currentThread().interrupt();
        jdbc.update("UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,next_attempt_at=now()+interval '15 minutes' WHERE instrument_id=?",id);
        return;
      }catch(Exception ex){
        // Never store provider response bodies, URLs or credentials.
        jdbc.update("UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,next_attempt_at=now()+interval '6 hours' WHERE instrument_id=?",id);
        if(OperatorFeedCooldown.record(jdbc,ex))return;
      }
    }
  }
}
