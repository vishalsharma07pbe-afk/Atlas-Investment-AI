package com.trading;
import static org.assertj.core.api.Assertions.assertThat;
import java.time.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import com.trading.market.*;
@SpringBootTest(properties={"ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","atlas.market.freshness.enabled=false","atlas.alerts.scheduler.enabled=false"})
class MarketSchedulerIntegrationTest {
 static final String EXTERNAL=System.getenv("TEST_DATABASE_URL");
 static final PostgreSQLContainer<?> PG=EXTERNAL==null?new PostgreSQLContainer<>("postgres:16-alpine").withInitScript("test-schema.sql"):null;
 static {if(PG!=null)PG.start();}
 @AfterAll static void stop(){if(PG!=null)PG.stop();}
 @DynamicPropertySource static void props(DynamicPropertyRegistry r){
  r.add("spring.datasource.url",()->EXTERNAL!=null?EXTERNAL:PG.getJdbcUrl());
  r.add("spring.datasource.username",()->EXTERNAL!=null?System.getenv("TEST_DATABASE_USERNAME"):PG.getUsername());
  r.add("spring.datasource.password",()->EXTERNAL!=null?System.getenv("TEST_DATABASE_PASSWORD"):PG.getPassword());
 }
 @Autowired JdbcTemplate jdbc;
 @Autowired MarketCalendarService calendar;
 @Autowired FreshnessService freshness;
 @Autowired MarketIngestionScheduler worker;
 @Test void workerPersistsTerminalFailureAtMaxRetry(){
  jdbc.update("INSERT INTO data_sources(source_code,display_name,source_class,access_mode,enabled) VALUES ('WORKER_FAIL_TEST','Worker failure test','MANUAL_FILE','LOCAL_UPLOAD',true) ON CONFLICT(source_code) DO UPDATE SET enabled=true");
  long src=jdbc.queryForObject("SELECT id FROM data_sources WHERE source_code='WORKER_FAIL_TEST'",Long.class);
  long id=jdbc.queryForObject("""
    INSERT INTO market_ingestion_queue(source_id,exchange_code,job_type,artifact_name,artifact_sha256,csv_payload)
    VALUES (?,'NSE','market-sessions','invalid.csv',repeat('f',64),?) RETURNING id
    """,Long.class,src,new byte[]{1,2,3});
  org.springframework.test.util.ReflectionTestUtils.setField(worker,"enabled",true);
  org.springframework.test.util.ReflectionTestUtils.setField(worker,"maxAttempts",1);
  try{worker.poll();}finally{org.springframework.test.util.ReflectionTestUtils.setField(worker,"enabled",false);}
  assertThat(jdbc.queryForObject("SELECT state FROM market_ingestion_queue WHERE id=?",String.class,id)).isEqualTo("FAILED");
  assertThat(jdbc.queryForObject("SELECT attempts FROM market_ingestion_queue WHERE id=?",Integer.class,id)).isEqualTo(1);
  assertThat(jdbc.queryForObject("SELECT status FROM market_worker_executions WHERE queue_id=?",String.class,id)).isEqualTo("FAILED");
  assertThat(jdbc.queryForObject("SELECT finished_at IS NOT NULL FROM market_worker_executions WHERE queue_id=?",Boolean.class,id)).isTrue();
 }
 @Test void seededHolidaysOverrideRegularSessions(){
  for(String ex:new String[]{"NSE","BSE"}){
   assertThat(calendar.isTradingDay(ex,LocalDate.of(2026,11,10))).isFalse();
   assertThat(calendar.isTradingDay(ex,LocalDate.of(2025,10,22))).isFalse();
   assertThat(jdbc.queryForObject("SELECT count(*) FROM exchange_holidays WHERE exchange_code=? AND holiday_date >= '2025-01-01' AND holiday_date < '2026-01-01'",Long.class,ex)).isEqualTo(14);
  }
 }
 @Test
 @org.springframework.transaction.annotation.Transactional
 void storedSessionContextDistinguishesPhasesAndUnknown(){
  LocalDate day=LocalDate.of(2026,11,25);
  jdbc.update("DELETE FROM market_sessions WHERE exchange_id=(SELECT id FROM exchanges WHERE code='NSE') AND session_date=?",day);
  Instant open=day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant();
  Instant close=day.atTime(15,30).atZone(MarketCalendarService.IST).toInstant();
  assertThat(calendar.sessionContext("NSE",open).get("phase")).isEqualTo("CALENDAR_UNVERIFIED");
  jdbc.update("""
    INSERT INTO market_sessions(exchange_id,session_date,session_type,is_trading_day,open_time,close_time)
    VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'REGULAR',true,?,?)
    """,day,java.sql.Timestamp.from(open),java.sql.Timestamp.from(close));
  assertThat(calendar.sessionContext("NSE",open.minusSeconds(3600))).containsEntry("phase","PRE_MARKET").containsEntry("open_at",open.toString());
  assertThat(calendar.sessionContext("NSE",open).get("phase")).isEqualTo("MARKET_HOURS");
  assertThat(calendar.sessionContext("NSE",close).get("phase")).isEqualTo("POST_MARKET");
  assertThat(calendar.sessionContext("NSE",LocalDate.of(2026,11,24).atTime(10,0).atZone(MarketCalendarService.IST).toInstant()).get("phase")).isEqualTo("CLOSED");
  jdbc.update("INSERT INTO market_sessions(exchange_id,session_date,session_type,is_trading_day) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'SPECIAL',true)",day);
  assertThat(calendar.sessionContext("NSE",open).get("phase")).isEqualTo("SPECIAL_SESSION_UNSUPPORTED");
 }
 @Test void duplicateCandleTimestampCannotCreateSecondRow(){
  jdbc.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'SCHEDTEST','EQ','MANUAL_CSV') ON CONFLICT DO NOTHING");
  long id=jdbc.queryForObject("SELECT id FROM instruments WHERE symbol='SCHEDTEST'",Long.class);
  for(int n=0;n<2;n++)jdbc.update("""
    INSERT INTO market_candles(instrument_id,timeframe,candle_time,open,high,low,close,volume)
    VALUES (?,'1d','2026-11-09T10:00:00Z',100,105,99,102,100)
    ON CONFLICT(instrument_id,timeframe,candle_time) DO UPDATE SET close=EXCLUDED.close
    """,id);
  assertThat(jdbc.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,id)).isEqualTo(1);
 }
 @Test void staleAlertIsDeduplicated(){
  jdbc.update("INSERT INTO data_sources(source_code,display_name,source_class,access_mode) VALUES ('SCHED_TEST','Scheduler test','MANUAL_FILE','LOCAL_UPLOAD') ON CONFLICT DO NOTHING");
  jdbc.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'FRESHTEST','EQ','MANUAL_CSV') ON CONFLICT DO NOTHING");
  long id=jdbc.queryForObject("SELECT id FROM instruments WHERE symbol='FRESHTEST'",Long.class);
  long src=jdbc.queryForObject("SELECT id FROM data_sources WHERE source_code='SCHED_TEST'",Long.class);
  // A seeded REGULAR session is needed for a deterministic market-open scan.
  jdbc.update("INSERT INTO market_sessions(exchange_id,session_date,session_type,is_trading_day) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'2026-11-16','REGULAR',true) ON CONFLICT DO NOTHING");
  Instant now=ZonedDateTime.of(2026,11,16,10,0,0,0,MarketCalendarService.IST).toInstant();
  jdbc.update("INSERT INTO instrument_source_freshness(instrument_id,source_id,last_synced_at) VALUES (?,?,?) ON CONFLICT(instrument_id,source_id) DO UPDATE SET last_synced_at=EXCLUDED.last_synced_at",id,src,java.sql.Timestamp.from(now.minus(Duration.ofDays(2))));
  freshness.scan(now);freshness.scan(now);
  assertThat(jdbc.queryForObject("SELECT count(*) FROM data_quality_events WHERE instrument_id=? AND source_id=? AND event_type='SOURCE_STALE' AND resolved_at IS NULL",Long.class,id,src)).isEqualTo(1);
 }
}
