package com.trading.api;

import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/data-health")
public class DataHealthController {
  private final JdbcTemplate jdbc;
  @org.springframework.beans.factory.annotation.Value("${atlas.market.feeds.enabled:false}") boolean scheduledFeeds;
  public DataHealthController(JdbcTemplate jdbc){this.jdbc=jdbc;}

  @GetMapping("/summary")
  public Map<String,Object> summary(){
    Map<String,Object> out=new LinkedHashMap<>();
    out.put("generatedAt",Instant.now());
    // Stored provider evidence is not a verified live websocket connection.
    var registry=jdbc.queryForMap("SELECT count(*) AS records,max(updated_at) AS latest FROM upstox_instrument_map");
    var nav=jdbc.queryForMap("""
      SELECT count(*) AS records,count(DISTINCT scheme_code) AS schemes,max(nav_date) AS latest
      FROM mutual_fund_nav WHERE source_code='AMFI' AND nav_date<=(now() AT TIME ZONE 'Asia/Kolkata')::date
      """);
    var daily=jdbc.queryForMap("""
      SELECT count(*) AS records,max((c.candle_time AT TIME ZONE 'Asia/Kolkata')::date) AS latest
      FROM market_candles c JOIN data_sources ds ON ds.id=c.source_id
      WHERE c.timeframe='1d' AND c.is_complete AND c.quality_status='PROVIDER_VALIDATED'
        AND ds.source_code='UPSTOX' AND (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date<(now() AT TIME ZONE 'Asia/Kolkata')::date
      """);
    out.put("providerMode",((Number)registry.get("records")).longValue()>0||((Number)daily.get("records")).longValue()>0?"UPSTOX_DATA_PRESENT":"MANUAL_OR_NOT_YET_SYNCED");
    out.put("liveMarketDataConnected",false);
    out.put("liveConnectionScope","NOT_OBSERVED_BY_BACKEND");
    out.put("scheduledFeedsEnabled",scheduledFeeds);
    out.put("operatorFeedCooldown",jdbc.queryForList("""
      SELECT scope,failure_code,failure_count,last_failure_at,blocked_until,
        blocked_until>now() AS blocked FROM operator_feed_cooldown
      """));
    out.put("publicFeedSchedule",jdbc.queryForList("""
      SELECT provider,CASE WHEN status='RUNNING' AND lease_until<=now() THEN 'RECOVERY_PENDING' ELSE status END AS status,
        attempts,interruptions,error_code,last_attempt_at,last_success_at,next_attempt_at
      FROM public_feed_schedule ORDER BY provider
      """));
    out.put("exchangeCalendar",jdbc.queryForList("""
      SELECT e.code AS exchange,count(s.session_date) AS recorded_sessions,
        max(s.session_date) FILTER (WHERE s.is_trading_day AND s.session_type='REGULAR'
          AND s.session_date<(now() AT TIME ZONE 'Asia/Kolkata')::date) AS latest_regular_session
      FROM exchanges e LEFT JOIN market_sessions s ON s.exchange_id=e.id
      WHERE e.code IN ('NSE','BSE') GROUP BY e.code ORDER BY e.code
      """));
    out.put("exchangeCalendarAttempts",jdbc.queryForList("""
      SELECT status,count(*) AS dates,max(attempted_at) AS latest_attempt,
        sum(rows_written) AS rows_written,error_code
      FROM exchange_calendar_attempts GROUP BY status,error_code ORDER BY status,error_code
      """));
    out.put("upstoxRegistry",registry);out.put("officialAmfiNav",nav);out.put("upstoxDailyHistory",daily);
    out.put("instrumentCount",jdbc.queryForObject("SELECT count(*) FROM instruments",Long.class));
    out.put("candleCount",jdbc.queryForObject("SELECT count(*) FROM market_candles WHERE timeframe='1d'",Long.class));
    out.put("unresolvedIssueCount",jdbc.queryForObject("SELECT count(*) FROM data_quality_events WHERE resolved_at IS NULL",Long.class));
    out.put("coverage",jdbc.queryForList("""
      SELECT e.code AS exchange,count(DISTINCT i.id) AS instruments,count(c.instrument_id) AS candle_count,
      min((c.candle_time AT TIME ZONE e.timezone)::date) AS first_date,max((c.candle_time AT TIME ZONE e.timezone)::date) AS latest_date
      FROM exchanges e LEFT JOIN instruments i ON i.exchange_id=e.id LEFT JOIN market_candles c ON c.instrument_id=i.id AND c.timeframe='1d'
      GROUP BY e.code ORDER BY e.code
      """));
    out.put("sources",jdbc.queryForList("""
      SELECT ds.source_code,ds.display_name,ds.access_mode,ds.license_scope,ds.verified_at,
        coalesce(i.instruments,0) AS instruments,coalesce(c.instruments_with_candles,0) AS instruments_with_candles,c.latest_candle
      FROM data_sources ds
      LEFT JOIN (SELECT source_id,count(*) AS instruments FROM instruments GROUP BY source_id) i ON i.source_id=ds.id
      LEFT JOIN (SELECT source_id,count(DISTINCT instrument_id) AS instruments_with_candles,max(candle_time) AS latest_candle
        FROM market_candles WHERE timeframe='1d' AND is_complete
          AND quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED') GROUP BY source_id) c ON c.source_id=ds.id
      WHERE ds.enabled ORDER BY ds.source_code
      """));
    out.put("recentRuns",jdbc.queryForList("""
      SELECT r.id,r.job_name,r.status,r.artifact_name,r.started_at,r.finished_at,r.records_seen,r.records_written,r.failure_count,r.error_message
      FROM ingestion_runs r ORDER BY r.started_at DESC LIMIT 20
      """));
    out.put("issues",jdbc.queryForList("""
      SELECT q.id,q.severity,q.event_type,q.observed_at,q.event_time,q.details,e.code AS exchange,i.symbol
      FROM data_quality_events q LEFT JOIN instruments i ON i.id=q.instrument_id LEFT JOIN exchanges e ON e.id=i.exchange_id
      WHERE q.resolved_at IS NULL ORDER BY q.observed_at DESC LIMIT 50
      """));
    return out;
  }
}
