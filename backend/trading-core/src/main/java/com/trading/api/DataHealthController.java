package com.trading.api;

import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/data-health")
public class DataHealthController {
  private final JdbcTemplate jdbc;
  public DataHealthController(JdbcTemplate jdbc){this.jdbc=jdbc;}

  @GetMapping("/summary")
  public Map<String,Object> summary(){
    Map<String,Object> out=new LinkedHashMap<>();
    out.put("generatedAt",Instant.now()); out.put("providerMode","MANUAL_CSV_ONLY"); out.put("liveMarketDataConnected",false);
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
      SELECT ds.source_code,ds.display_name,ds.access_mode,ds.license_scope,ds.verified_at,count(DISTINCT i.id) AS instruments,count(DISTINCT c.instrument_id) AS instruments_with_candles,max(c.candle_time) AS latest_candle
      FROM data_sources ds LEFT JOIN instruments i ON i.source_id=ds.id LEFT JOIN market_candles c ON c.source_id=ds.id
      WHERE ds.enabled GROUP BY ds.id ORDER BY ds.source_code
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
