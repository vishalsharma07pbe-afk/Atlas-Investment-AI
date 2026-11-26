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

@SpringBootTest(properties={"ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","atlas.market.freshness.enabled=false","atlas.alerts.scheduler.enabled=false","atlas.broker.holdings.enabled=false"})
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
 @Autowired BrokerHoldingsSyncService autoSync;
 @Autowired AmfiFeedService funds;
 @Autowired FundHistoryResearchService fundResearch;
 @Autowired DiscoveryHistoryScheduler discovery;
 @Autowired ExchangeCalendarSync exchangeCalendar;
 @Autowired MockMvc mvc;
 @MockitoBean FeedHttp http;
 @MockitoBean VersionedVaultReader vault;
 @AfterEach void clear(){SecurityContextHolder.clearContext();reset(http,vault);}
 private void user(UUID id){
  SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(id,null,List.of()));
 }
 private long seedStock(){
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'FEEDTEST','EQ','MANUAL_CSV','INE000A01001','EQ') ON CONFLICT DO NOTHING");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,isin,instrument_type) VALUES ('NSE_EQ|INE000A01001','NSE','FEEDTEST','INE000A01001','EQ') ON CONFLICT DO NOTHING");
  return db.queryForObject("SELECT id FROM instruments WHERE symbol='FEEDTEST'",Long.class);
 }
 @Test
 @org.springframework.transaction.annotation.Transactional
 void dateSpecificCalendarPersistsWithoutOverwritingExistingSessions()throws Exception{
  LocalDate day=LocalDate.of(2024,7,17);
  db.update("DELETE FROM market_sessions WHERE session_date=?",day);
  db.update("DELETE FROM exchange_holidays WHERE holiday_date=?",day);
  long open=day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant().toEpochMilli();
  long close=day.atTime(15,30).atZone(MarketCalendarService.IST).toInstant().toEpochMilli();
  db.update("UPDATE data_sources SET enabled=true WHERE source_code='UPSTOX'");
  when(http.text(contains("/market/timings/"+day),eq("test-operator"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":[{\"exchange\":\"NSE\",\"start_time\":"+open+",\"end_time\":"+close+"},{\"exchange\":\"BSE\",\"start_time\":"+open+",\"end_time\":"+close+"}]}");
  when(http.text(contains("/market/holidays/"+day),eq("test-operator"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":[]}");
  db.update("""
    INSERT INTO market_sessions(exchange_id,session_date,session_type,is_trading_day)
    VALUES ((SELECT id FROM exchanges WHERE code='BSE'),?,'REGULAR',false)
    """,day);
  var rows=exchangeCalendar.fetch(day,"test-operator");
  assertThat(exchangeCalendar.store(rows)).isEqualTo(1);
  assertThat(exchangeCalendar.store(rows)).isZero();
  assertThat(db.queryForObject("""
    SELECT count(*) FROM market_sessions s JOIN exchanges e ON e.id=s.exchange_id
    JOIN data_sources ds ON ds.id=s.source_id WHERE s.session_date=? AND e.code='NSE'
      AND s.is_trading_day AND ds.source_code='UPSTOX'
    """,Integer.class,day)).isEqualTo(1);
  assertThat(db.queryForObject("""
    SELECT s.is_trading_day FROM market_sessions s JOIN exchanges e ON e.id=s.exchange_id
    WHERE s.session_date=? AND e.code='BSE'
    """,Boolean.class,day)).isFalse();
  assertThat(new MarketCalendarService(db).isTradingDay("NSE",day)).isTrue();
 }
 @Test void benchmarkHistoryUsesStoredSessionClosesAndNeverReplacesManualSource()throws Exception{
  var service=new BenchmarkHistoryService(db,http,new org.springframework.transaction.support.TransactionTemplate(
    new org.springframework.jdbc.datasource.DataSourceTransactionManager(Objects.requireNonNull(db.getDataSource()))));
  LocalDate date=LocalDate.of(2025,1,6);
  long index=0;
  boolean previouslyEnabled=Boolean.TRUE.equals(db.queryForObject("SELECT enabled FROM data_sources WHERE source_code='UPSTOX'",Boolean.class));
  try{
   db.update("UPDATE data_sources SET enabled=true WHERE source_code='UPSTOX'");
   db.update("""
     INSERT INTO instruments(exchange_id,symbol,series,source,instrument_type,exchange_token,listing_status,active)
     VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'NIFTY50','INDEX','UPSTOX','INDEX','NSE_INDEX|Nifty 50','ACTIVE',true)
     ON CONFLICT DO NOTHING
     """);
   index=db.queryForObject("SELECT id FROM instruments WHERE exchange_token='NSE_INDEX|Nifty 50' AND instrument_type='INDEX'",Long.class);
   // Choose an isolated stored session if no preexisting row has been supplied.
   var open=java.sql.Timestamp.from(date.atTime(9,15).atZone(MarketCalendarService.IST).toInstant());
   var close=java.sql.Timestamp.from(date.atTime(15,30).atZone(MarketCalendarService.IST).toInstant());
   db.update("""
     INSERT INTO market_sessions(exchange_id,session_date,session_type,open_time,close_time,is_trading_day)
     VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'REGULAR',?,?,true)
     ON CONFLICT DO NOTHING
     """,date,open,close);
   when(http.text(contains("NSE_INDEX%7CNifty%2050/days/1"),eq("test-operator"),anyInt())).thenReturn("""
     {"status":"success","data":{"candles":[["2025-01-06T00:00:00+05:30",100,110,90,105,0,0]]}}
     """);
   assertThat(service.refresh(index,"test-operator",date,date)).isEqualTo(1);
   assertThat(db.queryForObject("SELECT close FROM market_candles WHERE instrument_id=? AND candle_time=?",BigDecimal.class,index,close)).isEqualByComparingTo("105");
   db.update("UPDATE market_candles SET source_id=(SELECT id FROM data_sources WHERE source_code='MANUAL_CSV'),close=99 WHERE instrument_id=? AND candle_time=?",index,close);
   assertThat(service.refresh(index,"test-operator",date,date)).isZero();
   assertThat(db.queryForObject("SELECT close FROM market_candles WHERE instrument_id=? AND candle_time=?",BigDecimal.class,index,close)).isEqualByComparingTo("99");
  }finally{
   if(index!=0)db.update("DELETE FROM market_candles WHERE instrument_id=? AND (candle_time AT TIME ZONE 'Asia/Kolkata')::date=?",index,date);
   db.update("UPDATE data_sources SET enabled=? WHERE source_code='UPSTOX'",previouslyEnabled);
  }
 }

 @Test void dailyAndIntradayUpsertsDeduplicateTimestamps()throws Exception{
  long instrument=seedStock();UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("only-in-memory");
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\"2026-11-13T09:15:00+05:30\",100,105,99,102,200]]}}");
  LocalDate day=LocalDate.of(2026,11,13);
  for(int i=0;i<2;i++)stocks.dailyCandles(owner,"NSE_EQ|INE000A01001",day,day);
  LocalDate recent=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\""+recent+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  for(String tf:List.of("1minute","15minute"))for(int i=0;i<2;i++)
   stocks.intradayCandles(owner,"NSE_EQ|INE000A01001",tf,recent,recent);
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(3);
  assertThat(db.queryForObject("SELECT count(DISTINCT timeframe) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(3);
  assertThat(db.queryForObject("SELECT count(*) FROM instrument_source_freshness WHERE instrument_id=?",Long.class,instrument)).isEqualTo(1);
 }
 @Test void invalidProviderCandlesAreRejectedAndAudited()throws Exception{
  long instrument=seedStock();UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("only-in-memory");
  when(http.text(contains("historical-candle"),eq("only-in-memory"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\"2026-11-13T09:15:00+05:30\",100,90,99,102,-1]]}}");
  LocalDate day=LocalDate.of(2026,11,13);
  long before=db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument);

  assertThatThrownBy(()->stocks.dailyCandles(owner,"NSE_EQ|INE000A01001",day,day))
   .isInstanceOf(IllegalStateException.class)
   .hasMessage("Provider returned no valid candles");
  assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(before);
  assertThat(db.queryForObject("SELECT count(*) FROM data_quality_events WHERE instrument_id=? AND event_type='PROVIDER_CANDLE_REJECTED'",Long.class,instrument)).isGreaterThanOrEqualTo(1);
  Map<String,Object> run=db.queryForMap("SELECT status,records_seen,records_written,failure_count FROM ingestion_runs WHERE source_revision=? ORDER BY started_at DESC LIMIT 1","UPSTOX_API:NSE_EQ|INE000A01001:1d:2026-11-13:2026-11-13");
  assertThat(run).containsEntry("status","FAILED");
  assertThat(((Number)run.get("records_seen")).longValue()).isEqualTo(1);
  assertThat(((Number)run.get("records_written")).longValue()).isZero();
  assertThat(((Number)run.get("failure_count")).longValue()).isEqualTo(1);
 }
 private void seedIdentity(String symbol,String isin){
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'EQ','UPSTOX',?,'EQ')",symbol,isin);
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,isin,instrument_type) VALUES (?,'NSE',?,?,'EQ')","NSE_EQ|"+isin,symbol,isin);
 }
 private static String holdingRow(String symbol,String isin,int qty,int price){
  return "{\"trading_symbol\":\""+symbol+"\",\"isin\":\""+isin+"\",\"exchange\":\"NSE\",\"instrument_token\":\"NSE_EQ|"+isin+"\",\"quantity\":"+qty+",\"average_price\":"+price+"}";
 }
 @Test void postHoldingsSyncIsScopedToAuthenticatedOwner()throws Exception{
  UUID a=UUID.randomUUID(),b=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'feed-owner-a@example.test','test'),(?,'feed-owner-b@example.test','test') ON CONFLICT DO NOTHING",a,b);
  seedIdentity("OWNERTEST","INE000A01005");
  when(vault.decrypt(a,"UPSTOX")).thenReturn("owner-a-secret");
  when(http.text(contains("long-term-holdings"),eq("owner-a-secret"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":["+holdingRow("OWNERTEST","INE000A01005",3,120)+"]}");
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
  seedIdentity("KEEP","INE000A01006");
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("owner-secret");
  when(http.text(contains("long-term-holdings"),eq("owner-secret"),anyInt()))
   .thenReturn("{\"status\":\"success\",\"data\":["+holdingRow("KEEP","INE000A01006",5,11)+"]}");

  assertThat(stocks.syncHoldings(owner)).isEqualTo(1);
  assertThat(db.queryForObject("SELECT quantity FROM personal_holdings WHERE user_id=? AND symbol='KEEP'",BigDecimal.class,owner)).isEqualByComparingTo("5");
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='STALE'",Long.class,owner)).isZero();
  assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='MANUAL'",Long.class,owner)).isEqualTo(1);
 }
 @Test void malformedHoldingsAndManualConflictsPreserveEntirePortfolio()throws Exception{
  UUID owner=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'safe-sync-owner@example.test','test')",owner);
  seedIdentity("SAFEKEEP","INE000A01007");seedIdentity("SAFEMANUAL","INE000A01008");
  db.update("INSERT INTO personal_holdings(user_id,symbol,asset_type,quantity,average_cost,notes) VALUES (?,'SAFEKEEP','EQUITY',1,10,'UPSTOX_SYNC'),(?,'SAFESTALE','EQUITY',2,20,'UPSTOX_SYNC'),(?,'SAFEMANUAL','EQUITY',3,30,'user note')",owner,owner,owner);
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("safe-test-token");
  String valid=holdingRow("SAFEKEEP","INE000A01007",5,11);
  for(String payload:List.of("{\"status\":\"error\",\"data\":[]}",
    "{\"status\":\"success\",\"data\":["+valid+",{\"trading_symbol\":\"INVALID\"}]}",
    "{\"status\":\"success\",\"data\":["+valid+","+valid+"]}",
    "{\"status\":\"success\",\"data\":["+valid+","+holdingRow("SAFEMANUAL","INE000A01008",5,11)+"]}")){
   when(http.text(contains("long-term-holdings"),eq("safe-test-token"),anyInt())).thenReturn(payload);
   assertThatThrownBy(()->stocks.syncHoldings(owner)).isInstanceOf(IllegalStateException.class);
   assertThat(db.queryForObject("SELECT quantity FROM personal_holdings WHERE user_id=? AND symbol='SAFEKEEP'",BigDecimal.class,owner)).isEqualByComparingTo("1");
   assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=?",Long.class,owner)).isEqualTo(3L);
  }
  when(http.text(contains("long-term-holdings"),eq("safe-test-token"),anyInt())).thenReturn("{\"status\":\"success\",\"data\":[]}");
  assertThat(stocks.syncHoldings(owner)).isZero();
  assertThat(db.queryForList("SELECT symbol FROM personal_holdings WHERE user_id=?",String.class,owner)).containsExactly("SAFEMANUAL");
 }
 @Test void exactHistoryMappingRejectsWrongIsinBeforeProviderRequest()throws Exception{
  seedIdentity("WRONGIDENTITY","INE000A01009");
  db.update("UPDATE upstox_instrument_map SET isin='INE000A01010' WHERE instrument_key='NSE_EQ|INE000A01009'");
  UUID owner=UUID.randomUUID();when(vault.decrypt(owner,"UPSTOX")).thenReturn("identity-test-token");
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  assertThatThrownBy(()->stocks.dailyCandles(owner,"NSE_EQ|INE000A01009",day,day)).isInstanceOf(IllegalArgumentException.class);
  verifyNoInteractions(http);
 }
 @Test void optedInHoldingsSyncPausesOnRejectedTokenAndResumesOnReplacement()throws Exception{
  UUID owner=UUID.randomUUID(),other=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'auto-sync-owner@example.test','test'),(?,'auto-sync-other@example.test','test')",owner,other);
  seedIdentity("AUTOSYNC","INE000A01011");
  for(UUID id:List.of(owner,other))db.update("""
    INSERT INTO broker_credentials(user_id,broker_name,encrypted_access_token,iv_nonce,token_expires_at,key_version)
    VALUES (?,'UPSTOX',decode('01','hex'),decode(repeat('00',12),'hex'),now()+interval '1 hour',1)
    """,id);
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("owner-test-token");
  when(http.text(contains("long-term-holdings"),eq("owner-test-token"),anyInt()))
    .thenThrow(new FeedHttp.ProviderHttpException(401));
  assertThat(autoSync.status(owner)).containsEntry("enabled",false).containsEntry("status","DISABLED");
  assertThat(autoSync.runOne()).isFalse();
  try{
   user(owner);
   mvc.perform(put("/api/v1/broker/upstox/holdings-sync").contentType("application/json").content("{\"enabled\":true}"))
     .andExpect(status().isOk()).andExpect(jsonPath("$.enabled").value(true));
   assertThat(autoSync.runOne()).isTrue();
   assertThat(autoSync.status(owner)).containsEntry("status","REAUTH_REQUIRED");
   assertThat(autoSync.runOne()).isFalse();
   verify(http,times(1)).text(contains("long-term-holdings"),eq("owner-test-token"),anyInt());
   user(other);
   mvc.perform(get("/api/v1/broker/upstox/holdings-sync")).andExpect(status().isOk()).andExpect(jsonPath("$.enabled").value(false));
   db.update("UPDATE broker_credentials SET updated_at=updated_at+interval '1 second' WHERE user_id=?",owner);
   when(vault.decrypt(owner,"UPSTOX")).thenReturn("replacement-test-token");
   when(http.text(contains("long-term-holdings"),eq("replacement-test-token"),anyInt()))
     .thenReturn("{\"status\":\"success\",\"data\":["+holdingRow("AUTOSYNC","INE000A01011",2,100)+"]}");
   assertThat(autoSync.runOne()).isTrue();
   assertThat(autoSync.status(owner)).containsEntry("status","SUCCESS");
   assertThat(autoSync.status(owner).get("last_success_at")).isNotNull();
   assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=? AND symbol='AUTOSYNC'",Long.class,owner)).isEqualTo(1L);
   assertThat(db.queryForObject("SELECT count(*) FROM personal_holdings WHERE user_id=?",Long.class,other)).isZero();
   assertThat(autoSync.runOne()).isFalse();
   db.update("UPDATE broker_credentials SET token_expires_at=now()-interval '1 second' WHERE user_id=?",owner);
   assertThat(autoSync.status(owner)).containsEntry("status","TOKEN_EXPIRED");
   assertThat(autoSync.runOne()).isFalse();
   verify(vault,never()).decrypt(other,"UPSTOX");
  }finally{autoSync.preference(owner,false);}
 }

 @Test void automaticSyncRecoversExpiredClaimAndRetainsRetryBackoff()throws Exception{
  UUID owner=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'sync-lease-owner@example.test','test')",owner);
  db.update("""
    INSERT INTO broker_credentials(user_id,broker_name,encrypted_access_token,iv_nonce,token_expires_at,key_version)
    VALUES (?,'UPSTOX',decode('01','hex'),decode(repeat('00',12),'hex'),now()+interval '1 hour',1)
    """,owner);
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("lease-test-token");
  when(http.text(contains("long-term-holdings"),eq("lease-test-token"),anyInt()))
    .thenThrow(new FeedHttp.ProviderHttpException(429));
  try{
   autoSync.preference(owner,true);
   db.update("""
     UPDATE broker_holdings_sync s SET status='RUNNING',claim_id=?,lease_until=now()-interval '1 second',
       next_attempt_at=now()-interval '1 second',credential_updated_at=b.updated_at
     FROM broker_credentials b WHERE s.user_id=? AND b.user_id=s.user_id
     """,UUID.randomUUID(),owner);
   assertThat(autoSync.status(owner)).containsEntry("status","RECOVERY_PENDING");
   assertThat(autoSync.runOne()).isTrue();
   assertThat(autoSync.status(owner)).containsEntry("status","RETRY").containsEntry("error_code","PROVIDER_RATE_LIMITED");
   assertThat(autoSync.runOne()).isFalse();
   assertThat(db.queryForObject("SELECT next_attempt_at>now() FROM broker_holdings_sync WHERE user_id=?",Boolean.class,owner)).isTrue();
   verify(http,times(1)).text(contains("long-term-holdings"),eq("lease-test-token"),anyInt());
  }finally{autoSync.preference(owner,false);}
 }
 @Test void staleOrRevokedHoldingsSyncClaimCannotAccessBroker()throws Exception{
  UUID owner=UUID.randomUUID();
  db.update("INSERT INTO atlas_users(id,email,password_hash) VALUES (?,'revoked-sync-owner@example.test','test')",owner);
  autoSync.preference(owner,false);
  assertThatThrownBy(()->stocks.syncClaimedHoldings(owner,UUID.randomUUID())).isInstanceOf(IllegalStateException.class);
  verifyNoInteractions(http,vault);
 }
 @Test void historicalNavCalculatesCagrRollingAndDrawdown()throws Exception{
  long code=987654321L;
  db.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name) VALUES (?,'Historical Test Fund') ON CONFLICT DO NOTHING",code);
  StringBuilder payload=new StringBuilder("{\"meta\":{\"scheme_code\":"+code+"},\"data\":[");
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
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type) VALUES ((SELECT id FROM exchanges WHERE code='BSE'),'DISCOVERYTEST','EQ','UPSTOX','INE000A01002','EQ')");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type,isin) VALUES ('BSE_EQ|INE000A01002','BSE','DISCOVERYTEST','EQ','INE000A01002')");
  long instrument=db.queryForObject("SELECT id FROM instruments WHERE symbol='DISCOVERYTEST'",Long.class);
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  when(http.text(contains("BSE_EQ%7CINE000A01002"),eq("discovery-test-token"),anyInt()))
    .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\""+day+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","discovery-test-token");
  try{
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",day);
    assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=?",Long.class,instrument)).isEqualTo(1);
    assertThat(db.queryForMap("SELECT status,rows_written FROM discovery_history_attempts WHERE instrument_id=?",instrument))
      .containsEntry("status","SUCCESS").containsEntry("rows_written",1);
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",day);
    verify(http,times(1)).text(contains("BSE_EQ%7CINE000A01002"),eq("discovery-test-token"),anyInt());
    verifyNoInteractions(vault);
  }finally{org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","");}
 }

 @Test
 @org.springframework.transaction.annotation.Transactional
 void discoveryBalancesExistingCoverageAndExpansion()throws Exception{
  LocalDate end=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  db.update("UPDATE instruments SET active=false WHERE exchange_id=(SELECT id FROM exchanges WHERE code='BSE')");
  String[] symbols={"MAINTAIN","EXPAND","UNSEEN"};
  String[] isins={"INE000A01901","INE000A01902","INE000A01903"};
  for(int i=0;i<symbols.length;i++){
   db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type,active) VALUES ((SELECT id FROM exchanges WHERE code='BSE'),?,'EQ','UPSTOX',?,'EQ',true)",symbols[i],isins[i]);
   db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type,isin) VALUES (?,'BSE',?,'EQ',?)","BSE_EQ|"+isins[i],symbols[i],isins[i]);
   if(i<2)db.update("""
     INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status)
     SELECT (SELECT id FROM instruments WHERE symbol=?),'1d',(?::date-g)::timestamp AT TIME ZONE 'Asia/Kolkata',
       (SELECT id FROM data_sources WHERE source_code='MANUAL_CSV'),100,105,99,102,200,true,'VALIDATED_MANUAL','RAW_UNADJUSTED'
     FROM generate_series(1,?) g
     """,symbols[i],end,i==0?210:50);
   when(http.text(contains("BSE_EQ%7C"+isins[i]),eq("coverage-test-token"),anyInt()))
     .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\""+end+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  }
  org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","coverage-test-token");
  try{
   org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",end);
   verify(http).text(contains("BSE_EQ%7C"+isins[0]),eq("coverage-test-token"),anyInt());
   verify(http).text(contains("BSE_EQ%7C"+isins[1]),eq("coverage-test-token"),anyInt());
   verify(http,never()).text(contains("BSE_EQ%7C"+isins[2]),eq("coverage-test-token"),anyInt());
  }finally{org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","");}
 }

 @Test
 @org.springframework.transaction.annotation.Transactional
 void discoveryRepairsKnownInteriorSessionDespiteCurrentLatestDate()throws Exception{
  LocalDate end=LocalDate.of(2026,11,20),missing=LocalDate.of(2026,11,18);
  String isin="INE000A01904";
  db.update("UPDATE instruments SET active=false WHERE exchange_id=(SELECT id FROM exchanges WHERE code='BSE')");
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type,active) VALUES ((SELECT id FROM exchanges WHERE code='BSE'),'GAPREPAIR','EQ','UPSTOX',?,'EQ',true)",isin);
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type,isin) VALUES (?,'BSE','GAPREPAIR','EQ',?)","BSE_EQ|"+isin,isin);
  long id=db.queryForObject("SELECT id FROM instruments WHERE symbol='GAPREPAIR'",Long.class);
  db.update("DELETE FROM market_sessions WHERE exchange_id=(SELECT id FROM exchanges WHERE code='BSE') AND session_date BETWEEN ? AND ?",end.minusMonths(12),end);
  for(LocalDate day:List.of(missing,end)){
    db.update("""
      INSERT INTO market_sessions(exchange_id,session_date,session_type,is_trading_day,open_time,close_time)
      VALUES ((SELECT id FROM exchanges WHERE code='BSE'),?,'REGULAR',true,?,?)
      """,day,java.sql.Timestamp.from(day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant()),
      java.sql.Timestamp.from(day.atTime(15,30).atZone(MarketCalendarService.IST).toInstant()));
  }
  db.update("""
    INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status)
    SELECT ?,'1d',((?::date-g)::timestamp+interval '9 hours 15 minutes') AT TIME ZONE 'Asia/Kolkata',
      (SELECT id FROM data_sources WHERE source_code='UPSTOX'),100,105,99,102,200,true,'PROVIDER_VALIDATED','RAW_UNADJUSTED'
    FROM generate_series(0,220) g WHERE g<>2
    """,id,end);
  when(http.text(contains("/"+end+"/"+missing),eq("gap-test-token"),anyInt()))
    .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\""+missing+"T09:15:00+05:30\",100,105,99,102,200]]}}");
  org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","gap-test-token");
  try{
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",end);
    verify(http).text(contains("/"+end+"/"+missing),eq("gap-test-token"),anyInt());
    assertThat(db.queryForObject("SELECT count(*) FROM market_candles WHERE instrument_id=? AND (candle_time AT TIME ZONE 'Asia/Kolkata')::date=?",Long.class,id,missing)).isEqualTo(1);
    db.update("UPDATE discovery_history_attempts SET next_attempt_at=now()-interval '1 second' WHERE instrument_id=?",id);
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",end);
    verify(http,times(1)).text(contains("BSE_EQ%7C"+isin),eq("gap-test-token"),anyInt());
    verifyNoInteractions(vault);
  }finally{org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","");}
 }

 @Test
 @org.springframework.transaction.annotation.Transactional
 void operatorHistoryCooldownPersistsAndBlocksOtherVenue()throws Exception{
  db.update("DELETE FROM operator_feed_cooldown");
  db.update("UPDATE instruments SET active=false WHERE exchange_id=(SELECT id FROM exchanges WHERE code='NSE')");
  String isin="INE000A01905";
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type,active) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'COOLDOWNTEST','EQ','UPSTOX',?,'EQ',true)",isin);
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type,isin) VALUES (?,'NSE','COOLDOWNTEST','EQ',?)","NSE_EQ|"+isin,isin);
  LocalDate end=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  when(http.text(contains("NSE_EQ%7C"+isin),eq("cooldown-test-token"),anyInt()))
    .thenThrow(new FeedHttp.ProviderHttpException(429,600));
  org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","cooldown-test-token");
  try{
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","NSE",end);
    assertThat(db.queryForMap("SELECT failure_code,failure_count,blocked_until>now() AS blocked FROM operator_feed_cooldown"))
      .containsEntry("failure_code","PROVIDER_RATE_LIMITED").containsEntry("failure_count",1).containsEntry("blocked",true);
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(discovery,"refreshExchange","BSE",end);
    verify(http,times(1)).text(anyString(),eq("cooldown-test-token"),anyInt());
    verifyNoInteractions(vault);
  }finally{org.springframework.test.util.ReflectionTestUtils.setField(discovery,"accessToken","");}
 }

 @Test
 @org.springframework.transaction.annotation.Transactional
 void publicCatalogJobsDeduplicateRecoverAndIsolateProviders()throws Exception{
  db.update("UPDATE public_feed_schedule SET status='IDLE',attempts=0,claim_id=NULL,lease_until=NULL,next_attempt_at=now(),error_code=NULL");
  var stockMock=mock(UpstoxFeedService.class);
  var fundMock=mock(AmfiFeedService.class);
  var scheduler=new FeedRefreshScheduler(db,stockMock,fundMock,mock(MarketCalendarService.class),
    new org.springframework.transaction.support.TransactionTemplate(
      new org.springframework.jdbc.datasource.DataSourceTransactionManager(Objects.requireNonNull(db.getDataSource()))));
  when(stockMock.syncMaster()).thenThrow(new FeedHttp.ProviderHttpException(429,600)).thenReturn(3);
  when(fundMock.refresh()).thenReturn(5);
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","UPSTOX","MASTER",false)).isTrue();
  assertThat(db.queryForMap("SELECT status,attempts,error_code FROM public_feed_schedule WHERE provider='UPSTOX'"))
    .containsEntry("status","RETRY").containsEntry("attempts",1).containsEntry("error_code","PROVIDER_RATE_LIMITED");
  assertThat(db.queryForObject("SELECT next_attempt_at>=now()+interval '599 seconds' FROM public_feed_schedule WHERE provider='UPSTOX'",Boolean.class)).isTrue();
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","UPSTOX","MASTER_AUTO",false)).isFalse();
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","AMFI","NAV",false)).isTrue();
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","AMFI","NAV_AUTO",false)).isFalse();
  // Simulate an interrupted persisted run, then recover it through the retry path.
  UUID old=UUID.randomUUID();
  db.update("UPDATE public_feed_schedule SET status='RUNNING',claim_id=?,lease_until=now()-interval '1 second',next_attempt_at=now()-interval '1 second' WHERE provider='UPSTOX'",old);
  db.update("INSERT INTO market_provider_runs(provider,job_name,status,claim_id) VALUES ('UPSTOX','MASTER_RETRY','RUNNING',?)",old);
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","UPSTOX","MASTER_RETRY",true)).isTrue();
  assertThat(db.queryForMap("SELECT status,attempts,interruptions FROM public_feed_schedule WHERE provider='UPSTOX'"))
    .containsEntry("status","SUCCESS").containsEntry("attempts",2);
  assertThat(db.queryForObject("SELECT status FROM market_provider_runs WHERE claim_id=?",String.class,old)).isEqualTo("FAILED");
  assertThat((Boolean)org.springframework.test.util.ReflectionTestUtils.invokeMethod(scheduler,"attempt","UPSTOX","MASTER_RETRY",true)).isFalse();
  verify(stockMock,times(2)).syncMaster();
  verify(fundMock,times(1)).refresh();
 }

 @Test void providerHistoryDoesNotOverwriteAdjustedManualCandle()throws Exception{
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'ADJUSTEDTEST','EQ','MANUAL_CSV','INE000A01003','EQ')");
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type,isin) VALUES ('NSE_EQ|INE000A01003','NSE','ADJUSTEDTEST','EQ','INE000A01003')");
  long instrument=db.queryForObject("SELECT id FROM instruments WHERE symbol='ADJUSTEDTEST'",Long.class);
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  var stamp=java.sql.Timestamp.from(day.atTime(9,15).atZone(MarketCalendarService.IST).toInstant());
  db.update("INSERT INTO market_candles(instrument_id,timeframe,candle_time,source_id,open,high,low,close,volume,is_complete,quality_status,adjustment_status) VALUES (?,'1d',?,(SELECT id FROM data_sources WHERE source_code='MANUAL_CSV'),100,110,95,105,200,true,'VALIDATED_MANUAL','ADJUSTED')",instrument,stamp);
  UUID owner=UUID.randomUUID();
  when(vault.decrypt(owner,"UPSTOX")).thenReturn("owner-test-token");
  when(http.text(contains("NSE_EQ%7CINE000A01003"),eq("owner-test-token"),anyInt()))
    .thenReturn("{\"status\":\"success\",\"data\":{\"candles\":[[\""+day+"T09:15:00+05:30\",200,210,190,205,300]]}}");
  assertThatThrownBy(()->stocks.dailyCandles(owner,"NSE_EQ|INE000A01003",day,day)).isInstanceOf(IllegalStateException.class);
  assertThat(db.queryForMap("SELECT close,adjustment_status FROM market_candles WHERE instrument_id=?",instrument))
    .containsEntry("adjustment_status","ADJUSTED");
  assertThat(db.queryForObject("SELECT close FROM market_candles WHERE instrument_id=?",BigDecimal.class,instrument)).isEqualByComparingTo("105");
 }


 @Test
 @org.springframework.transaction.annotation.Transactional
 void amfiPreservesSchemeIdentityAndRejectsConflictingHistory()throws Exception{
  long code=987650456L;
  LocalDate today=LocalDate.now(MarketCalendarService.IST);
  var fmt=java.time.format.DateTimeFormatter.ofPattern("dd-MMM-uuuu",Locale.ENGLISH);
  String prefix="Open Ended Schemes(Equity Scheme - Large Cap Fund)\nExample Mutual Fund\n";
  String row=code+";INF000A01001;-;Example Fund;Direct Plan;Growth Option;125.50;"+today.format(fmt);
  assertThat(funds.importNav(prefix+row)).isEqualTo(1);
  var scheme=db.queryForMap("SELECT amfi_plan,amfi_option,amfi_metadata_date,category,amc_name FROM mutual_fund_schemes WHERE scheme_code=?",code);
  assertThat(scheme).containsEntry("amfi_plan","DIRECT").containsEntry("amfi_option","GROWTH").containsEntry("category","Open Ended Schemes(Equity Scheme - Large Cap Fund)").containsEntry("amc_name","Example Mutual Fund");
  assertThatThrownBy(()->funds.importNav(prefix+row.replace("INF000A01001","INF000A01002"))).isInstanceOf(IllegalStateException.class);
  assertThat(db.queryForObject("SELECT isin_growth FROM mutual_fund_schemes WHERE scheme_code=?",String.class,code)).isEqualTo("INF000A01001");
 }
 @Test void historicalNavRequiresDeclaredIdentityAndUniqueDates()throws Exception{
  long code=987650457L;
  LocalDate day=LocalDate.now(MarketCalendarService.IST).minusDays(1);
  db.update("INSERT INTO mutual_fund_schemes(scheme_code,scheme_name) VALUES (?,'History Identity Test')",code);
  String formatted=day.format(java.time.format.DateTimeFormatter.ofPattern("dd-MM-yyyy"));
  String item="{\"date\":\""+formatted+"\",\"nav\":\"100\"}";
  for(String payload:List.of("{\"data\":["+item+"]}",
     "{\"meta\":{\"scheme_code\":1},\"data\":["+item+"]}",
     "{\"meta\":{\"scheme_code\":"+code+"},\"data\":["+item+","+item.replace("100","200")+"]}")){
   when(http.text(contains("api.mfapi.in/mf/"+code),isNull(),anyInt())).thenReturn(payload);
   assertThatThrownBy(()->funds.history(code)).isInstanceOf(IllegalStateException.class);
   assertThat(db.queryForObject("SELECT count(*) FROM mutual_fund_nav WHERE scheme_code=?",Long.class,code)).isZero();
  }
  when(http.text(contains("api.mfapi.in/mf/"+code),isNull(),anyInt()))
    .thenReturn("{\"meta\":{\"scheme_code\":"+code+"},\"data\":["+item+","+item+"]}");
  assertThat(funds.history(code)).isEqualTo(1);
  assertThat(db.queryForObject("SELECT count(*) FROM mutual_fund_nav WHERE scheme_code=?",Long.class,code)).isEqualTo(1L);
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
  String symbol="INTRADAYTEST",key="NSE_EQ|INE000A01004";
  db.update("INSERT INTO instruments(exchange_id,symbol,series,source,isin,instrument_type) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),?,'EQ','TEST','INE000A01004','EQ')",symbol);
  db.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,isin,instrument_type) VALUES (?,'NSE',?,'INE000A01004','EQ')",key,symbol);
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
