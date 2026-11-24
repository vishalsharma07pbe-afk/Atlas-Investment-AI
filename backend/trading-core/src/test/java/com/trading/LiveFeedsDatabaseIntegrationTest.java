package com.trading;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import com.trading.api.*;
import com.trading.market.*;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;

@SpringBootTest(properties={"ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","atlas.market.freshness.enabled=false","atlas.alerts.scheduler.enabled=false"})
@AutoConfigureMockMvc(addFilters=false)
class LiveFeedsDatabaseIntegrationTest {
 static final String EXTERNAL=System.getenv("TEST_DATABASE_URL");
 static final PostgreSQLContainer<?> PG=EXTERNAL==null?new PostgreSQLContainer<>("postgres:16-alpine").withInitScript("test-schema.sql"):null;
 static {if(PG!=null)PG.start();}
 @AfterAll static void stop(){if(PG!=null)PG.stop();}
 @DynamicPropertySource static void props(DynamicPropertyRegistry r){
  r.add("spring.datasource.url",()->EXTERNAL!=null?EXTERNAL:PG.getJdbcUrl());
  r.add("spring.datasource.username",()->EXTERNAL!=null?System.getenv("TEST_DATABASE_USERNAME"):PG.getUsername());
  r.add("spring.datasource.password",()->EXTERNAL!=null?System.getenv("TEST_DATABASE_PASSWORD"):PG.getPassword());
 }
 @Autowired JdbcTemplate db;
 @Autowired UpstoxFeedService stocks;
 @Autowired AmfiFeedService funds;
 @Autowired FundHistoryResearchService fundResearch;
 @Autowired DiscoveryHistoryScheduler discovery;
 @Autowired MockMvc mvc;
 @MockitoBean FeedHttp http;
 @MockitoBean VersionedVaultReader vault;
 @AfterEach void clear(){SecurityContextHolder.clearContext();reset(http,vault);}
 private void user(UUID id){
  SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(id,null,List.of()));
 }
 private long seedStock(){
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'FEEDTEST','EQ','MANUAL_CSV') ON CONFLICT DO NOTHING");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol) VALUES ('NSE_EQ|FEEDTEST','NSE','FEEDTEST') ON CONFLICT DO NOTHING");
  return db.queryForObject("SELECT id FROM instruments WHERE symbol='FEEDTEST'",Long.class);
 }
 @Test void dailyAndIntradayUpsertsDeduplicateTimestamps()throws Exception{
  long instrument=seedStock();UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("only-in-memory");
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"data\":{\"candles\":[[\"2026-11-13T09:15:00+05:30\",100,105,99,102,200]]}}");
  LocalDate day=LocalDate.of(2026,11,13);
  for(int i=0;i<2;i++)stocks.dailyCandles(owner,"NSE_EQ|FEEDTEST",day,day);
  LocalDate recent=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"data\":{\"candles\":[[\""+recent+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  for(String tf:List.of("1minute","15minute"))for(int i=0;i<2;i++)
   stocks.intradayCandles(owner,"NSE_EQ|FEEDTEST",tf,recent,recent);
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(3);
  assertThat(db.queryForObject("SELECT count(DISTINCT timeframe) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(3);
  assertThat(db.queryForObject("SELECT count(*) FROM instrument_source_freshness WHERE instrument_id=?",Long.class,instrument)).isEqualTo(1);
 }
 @Test void invalidProviderCandlesAreRejectedAndAudited()throws Exception{
  long instrument=seedStock();UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("only-in-memory");
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"data\":{\"candles\":[[\"2026-11-13T09:15:00+05:30\",100,90,99,102,-1]]}}");
  LocalDate day=LocalDate.of(2026,11,13);
  long before=db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument);

  assertThatThrownBy(()->stocks.dailyCandles(owner,"NSE_EQ|FEEDTEST",day,day))
   .isInstanceOf(IllegalStateException.class)
   .hasMessage("Provider returned no valid candles");
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(before);
  assertThat(db.queryForObject("SELECT count(*) FROM data_quality_events WHERE instrument_id=? AND event_type='PROVIDER_CANDLE_REJECTED'",Long.class,instrument)).isGreaterThanOrEqualTo(1);
  Map<String,Object> run=db.queryForMap("SELECT status,records_seen,records_written,failure_count FROM ingestion_runs WHERE source_revision=? ORDER BY started_at DESC LIMIT 1","UPSTOX_API:NSE_EQ|FEEDTEST:1d:2026-11-13:2026-11-13");
  assertThat(run).containsEntry("status","FAILED");
  assertThat(((Number)run.get("records_seen")).longValue()).isEqualTo(1);
  assertThat(((Number)run.get("records_written")).longValue()).isZero();
  assertThat(((Number)run.get("failure_count")).longValue()).isEqualTo(1);
 }
 @Test void postHoldingsSyncIsScopedToAuthenticatedOwner()throws Exception{
  UUID a=UUID.randomUUID(),b=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'feed-owner-a@example.test','test'),(?,'feed-owner-b@example.test','test') ON CONFLICT DO NOTHING",a,b);
  when(vault.decrypt(a,"UPSTOX")).thenReturn("owner-a-secret");
  when(http.text(contains("long-term-holdings"),eq("owner-a-secret"),anyInt()))
   .thenReturn("{\"data\":[{\"trading_symbol\":\"OWNERTEST\",\"quantity\":3,\"average_price\":120}]}");
  user(a);
  mvc.perform(post("/api/v1/portfolio/sync/upstox")).andExpect(status().isOk()).andExpect(jsonPath("$.synced").value(1));
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='OWNERTEST'",Long.class,a)).isEqualTo(1);
  user(b);
  mvc.perform(get("/api/v1/portfolio/holdings")).andExpect(status().isOk()).andExpect(content().json("[]"));
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='OWNERTEST'",Long.class,b)).isZero();
 }
 @Test void holdingsSyncRemovesOnlyStaleBrokerPositions()throws Exception{
  UUID owner=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'reconcile-owner@example.test','test')",owner);
  db.update("INSERT INTO personal_holdings(user_id,symbol,asset_type,quantity,average_cost,notes) VALUES (?,'KEEP','EQUITY',1,10,'UPSTOX_SYNC'),(?,'STALE','EQUITY',2,20,'UPSTOX_SYNC'),(?,'MANUAL','EQUITY',3,30,'user note')",owner,owner,owner);
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("owner-secret");
  when(http.text(contains("long-term-holdings"),eq("owner-secret"),anyInt()))
   .thenReturn("{\"data\":[{\"trading_symbol\":\"KEEP\",\"quantity\":5,\"average_price\":11}]}");

  assertThat(stocks.syncHoldings(owner)).isEqualTo(1);
  assertThat(db.queryForObject("SELECT quantity FROM personal_holdings WHERE user_id=? AND symbol='KEEP'",BigDecimal.class,owner)).isEqualByComparingTo("5");
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='STALE'",Long.class,owner)).isZero();
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='MANUAL'",Long.class,owner)).isEqualTo(1);
 }
 @Test void historicalNavCalculatesCagrRollingAndDrawdown()throws Exception{
  long code=987654321L;
  db.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name) VALUES (?,'Historical Test Fund') ON CONFLICT DO NOTHING",code);
  StringBuilder payload=new StringBuilder("{\"data\":[");
  LocalDate start=LocalDate.of(2020,1,1);
  for(int i=0;i<=72;i++){
   LocalDate date=start.plusMonths(i);
   double value=100*Math.pow(1.10,i/12.0)*(i==30?0.75:1.0);
   if(i>0)payload.append(',');
   payload.append("{\"date\":\"").append(date.format(java.time.format.DateTimeFormatter.ofPattern("dd-MM-yyyy"))).append("\",\"nav\":\"").append(String.format(Locale.ROOT,"%.6f",value)).append("\"}");
  }
  payload.append("]}");
  when(http.text(contains("api.mfapi.in/mf/"),isNull(),anyInt())).thenReturn(payload.toString());
  assertThat(funds.history(code)).isEqualTo(73);
  Map<String,Object> metrics=funds.performance(code);
  for(String key:List.of("cagr1Y","cagr3Y","cagr5Y"))
   assertThat((Double)metrics.get(key)).isBetween(0.08,0.12);
  assertThat((List<?>)metrics.get("rolling1Y")).isNotEmpty();
  assertThat((List<?>)metrics.get("rolling3Y")).isNotEmpty();
  assertThat(((BigDecimal)metrics.get("maxDrawdown")).doubleValue()).isLessThan(-0.20);
 }

 @Test void discoveryBackfillsMappedEquityWithoutBorrowingOwnerToken()throws Exception{
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='BSE'),'DISCOVERYTEST','EQ','UPSTOX')");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type) VALUES ('BSE_EQ|DISCOVERYTEST','BSE','DISCOVERYTEST','EQ')");
  long instrument=db.queryForObject("SELECT id FROM instruments WHERE symbol='DISCOVERYTEST'",Long.class);
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  when(http.text(contains("BSE_EQ%7CDISCOVERYTEST"),eq("discovery-test-token"),anyInt()))
    .thenReturn("{\"data\":{\"candles\":[[\""+day+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","discovery-test-token");
  try{
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",day);
    assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(1);
    assertThat(db.queryForMap("SELECT status,rows_written FROM discovery_history_attempts WHERE instrument_id=?",instrument))
      .containsEntry("status","SUCCESS").containsEntry("rows_written",1);
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",day);
    verify(http,times(1)).text(contains("BSE_EQ%7CDISCOVERYTEST"),eq("discovery-test-token"),anyInt());
    verifyNoInteractions(vault);
  }finally{org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","");}
 }

 @Test void providerHistoryDoesNotOverwriteAdjustedManualCandle()throws Exception{
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'ADJUSTEDTEST','EQ','MANUAL_CSV')");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type) VALUES ('NSE_EQ|ADJUSTEDTEST','NSE','ADJUSTEDTEST','EQ')");
  long instrument=db.queryForObject("SELECT id FROM instruments WHERE symbol='ADJUSTEDTEST'",Long.class);
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  var stamp=java.sql.Timestamp.from(day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant());
  db.update("INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status) VALUES (?,'1d',?,(SELECT id FROM data_sources WHERE source_code='MANUAL_CSV'),100,110,95,105,200,true,'VALIDATED_MANUAL','ADJUSTED')",instrument,stamp);
  UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("owner-test-token");
  when(http.text(contains("NSE_EQ%7CADJUSTEDTEST"),eq("owner-test-token"),anyInt()))
    .thenReturn("{\"data\":{\"candles\":[[\""+day+"T09:15:00+05:30\",200,210,190,205,300]]}}");
  assertThatThrownBy(()->stocks.dailyCandles(owner,"NSE_EQ|ADJUSTEDTEST",day,day)).isInstanceOf(IllegalStateException.class);
  assertThat(db.queryForMap("SELECT close,adjustment_status FROM market_candles WHERE instrument_id=?",instrument))
    .containsEntry("adjustment_status","ADJUSTED");
  assertThat(db.queryForObject("SELECT close FROM market_candles WHERE instrument_id=?",BigDecimal.class,instrument)).isEqualByComparingTo("105");
 }


 @Test void fundHistoryWatchUsesOfficialCategoryAndPreservesAmfiNav()throws Exception{
  long code=987650123L;
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  db.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name,category) VALUES (?,'Example Direct Plan Growth','Open Ended Schemes(Equity Scheme - Large Cap Fund)')",code);
  db.update("""
    INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code)
    SELECT ?,?::date-g,120-g*0.01,CASE WHEN g=0 THEN 'AMFI' ELSE 'MFAPI' END
    FROM generate_series(0,1100) g
    """,code,today);
  var watch=fundResearch.watch("LARGE_CAP");
  assertThat(watch).containsEntry("status","HISTORICAL_WATCH_ONLY");
  assertThat((List<?>)watch.get("items")).hasSize(1);
  assertThat(((List<?>)watch.get("items")).getFirst()).isInstanceOf(Map.class);
  assertThat(((Map<?,?>)((List<?>)watch.get("items")).getFirst()).get("scheme_code")).isEqualTo(code);
  assertThat((List<?>)fundResearch.watch("SMALL_CAP").get("items")).isEmpty();
  String day=today.format(java.time.format.DateTimeFormatter.ofPattern("dd-MM-yyyy"));
  when(http.text(contains("api.mfapi.in/mf/"+code),isNull(),anyInt()))
    .thenReturn("{\"meta\":{\"scheme_code\":"+code+"},\"data\":[{\"date\":\""+day+"\",\"nav\":\"999\"}]}");
  funds.history(code);
  assertThat(db.queryForObject("SELECT nav FROM mutual_fund_nav WHERE scheme_code=? AND nav_date=?",BigDecimal.class,code,today)).isEqualByComparingTo("120");
 }


 @Test void healthReportsStoredUpstoxAndAmfiEvidenceWithoutClaimingLiveConnection(){
  seedStock();
  long code=987654111L;
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  db.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name) VALUES (?,'Health Test Direct Growth')",code);
  db.update("INSERT INTO mutual_fund_nav(scheme_code,nav_date,nav,source_code) VALUES (?,?,100,'AMFI')",code,today);
  var health=new DataHealthController(db).summary();
  assertThat(health).containsEntry("providerMode","UPSTOX_DATA_PRESENT").containsEntry("liveMarketDataConnected",false);
  assertThat(((Number)((Map<?,?>)health.get("officialAmfiNav")).get("records")).longValue()).isGreaterThanOrEqualTo(1);
  assertThat(((Number)((Map<?,?>)health.get("upstoxRegistry")).get("records")).longValue()).isGreaterThanOrEqualTo(1);
 }

 @Test void currentSessionIngestionExcludesFormingBars()throws Exception{
  String symbol="INTRADAYTEST",key="NSE_EQ|INTRADAYTEST";
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'EQ','TEST')",symbol);
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol) VALUES (?,'NSE',?)",key,symbol);
  LocalDate day=LocalDate.now(MarketCalendarService.IST);
  Instant cutoff=day.atTime(9,50).atZone(MarketCalendarService.IST).toInstant();
  String payload="{\"status\":\"success\",\"data\":{\"candles\":["
    +"[\""+day+"T09:45:00+05:30\",100,102,99,101,300],"
    +"[\""+day+"T09:30:00+05:30\",100,102,99,101,200],"
    +"[\""+day+"T09:15:00+05:30\",100,102,99,101,100]]}}";
  when(http.text(contains("/intraday/"),eq("test-only"),anyInt())).thenReturn(payload);
  Integer written=org.springframework.test.util.ReflectionTestUtils.invokeMethod(stocks,"discoveryIntradayCandles","test-only",key,cutoff);
  assertThat(written).isEqualTo(2);
  long instrument=db.queryForObject("SELECT id FROM instruments WHERE symbol=?",Long.class,symbol);
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=? AND timeframe='15minute' AND is_complete",Long.class,instrument)).isEqualTo(2L);
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=? AND (candle_time AT TIME ZONE 'Asia/Kolkata')::time='09:45:00'",Long.class,instrument)).isZero();
  verifyNoInteractions(vault);
 }
}
