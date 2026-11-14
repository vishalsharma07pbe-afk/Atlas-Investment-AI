package com.trading.market;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
@Service public class FreshnessService {
 private final JdbcTemplate jdbc;private final MarketCalendarService calendar;
 @Value("${atlas.market.freshness.max-age-minutes:30}") long threshold;
 public FreshnessService(JdbcTemplate jdbc,MarketCalendarService calendar){this.jdbc=jdbc;this.calendar=calendar;}
 @Scheduled(fixedDelayString="${atlas.market.freshness.poll-ms:60000}") public void scan(){scan(Instant.now());}
 public void scan(Instant now){
  scanFunds(now);
  for(String exchange:List.of("NSE","BSE")){
   if(!calendar.isMarketOpen(exchange,now))continue;
   for(Map<String,Object> r:jdbc.queryForList("SELECT f.instrument_id,f.source_id,f.last_synced_at FROM instrument_source_freshness f JOIN instruments i ON i.id=f.instrument_id JOIN exchanges e ON e.id=i.exchange_id WHERE e.code=? AND i.active",exchange)){
    long instrument=((Number)r.get("instrument_id")).longValue(),source=((Number)r.get("source_id")).longValue();Instant synced=((java.sql.Timestamp)r.get("last_synced_at")).toInstant();
    if(synced.isBefore(now.minus(Duration.ofMinutes(threshold))))
     jdbc.update("INSERT INTO data_quality_events(source_id,instrument_id,severity,event_type,details) VALUES (?,?,'WARNING','SOURCE_STALE',jsonb_build_object('lastSyncedAt',?::text,'maxAgeMinutes',?::bigint)) ON CONFLICT (instrument_id,source_id,event_type) WHERE event_type='SOURCE_STALE' AND resolved_at IS NULL DO NOTHING",source,instrument,synced.toString(),threshold);
    else jdbc.update("UPDATE data_quality_events SET resolved_at=now() WHERE source_id=? AND instrument_id=? AND event_type='SOURCE_STALE' AND resolved_at IS NULL",source,instrument);
   }
  }
 }
 public LocalDate expectedNavDate(Instant now){
  ZonedDateTime z=now.atZone(MarketCalendarService.IST);
  LocalDate candidate=z.toLocalDate();
  if(z.toLocalTime().isBefore(LocalTime.of(22,0)))candidate=candidate.minusDays(1);
  for(int i=0;i<370;i++,candidate=candidate.minusDays(1))
   if(calendar.isTradingDay("NSE",candidate))return candidate;
  throw new IllegalStateException("No attested NSE trading session for AMFI NAV");
 }
 public void scanFunds(Instant now){
  LocalDate expected;
  try{expected=expectedNavDate(now);}catch(IllegalStateException missing){return;}
  for(Map<String,Object> row:jdbc.queryForList("""
    SELECT s.scheme_code, max(n.nav_date) AS latest_nav_date
    FROM mutual_fund_schemes s LEFT JOIN mutual_fund_nav n ON n.scheme_code=s.scheme_code
    GROUP BY s.scheme_code
    """)){
   long code=((Number)row.get("scheme_code")).longValue();
   java.sql.Date last=(java.sql.Date)row.get("latest_nav_date");
   boolean stale=last==null||last.toLocalDate().isBefore(expected);
   if(stale)jdbc.update("""
     INSERT INTO mutual_fund_freshness_alerts(scheme_code,expected_nav_date,observed_at)
     VALUES (?,?,?)
     ON CONFLICT(scheme_code) WHERE resolved_at IS NULL
     DO UPDATE SET expected_nav_date=EXCLUDED.expected_nav_date
     """,code,expected,java.sql.Timestamp.from(now));
   else jdbc.update("UPDATE mutual_fund_freshness_alerts SET resolved_at=? WHERE scheme_code=? AND resolved_at IS NULL",java.sql.Timestamp.from(now),code);
  }
 }
 public List<Map<String,Object>> mutualFundSnapshot(){
  return jdbc.queryForList("""
    SELECT 'MUTUAL_FUND' asset_type,s.scheme_code,s.scheme_name,s.last_synced_at,
      (SELECT max(nav_date) FROM mutual_fund_nav n WHERE n.scheme_code=s.scheme_code) latest_nav_date,
      a.id alert_id,(a.id IS NOT NULL) stale,a.expected_nav_date
    FROM mutual_fund_schemes s LEFT JOIN mutual_fund_freshness_alerts a
      ON a.scheme_code=s.scheme_code AND a.resolved_at IS NULL
    ORDER BY s.scheme_name
    """);
 }
 public List<Map<String,Object>> snapshot(){return jdbc.queryForList("SELECT e.code exchange,i.symbol,f.instrument_id,ds.source_code,f.last_synced_at,f.latest_candle_at,f.source_revision,q.id alert_id FROM instrument_source_freshness f JOIN instruments i ON i.id=f.instrument_id JOIN exchanges e ON e.id=i.exchange_id JOIN data_sources ds ON ds.id=f.source_id LEFT JOIN data_quality_events q ON q.instrument_id=f.instrument_id AND q.source_id=f.source_id AND q.event_type='SOURCE_STALE' AND q.resolved_at IS NULL ORDER BY e.code,i.symbol,ds.source_code");}
}
