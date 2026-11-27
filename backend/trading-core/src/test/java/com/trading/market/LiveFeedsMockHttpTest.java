package com.trading.market;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.trading.api.VersionedVaultReader;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
class LiveFeedsMockHttpTest {
 @Test void masterMapsUpstoxNseBse(){
  JdbcTemplate db=mock(JdbcTemplate.class);FeedHttp http=mock(FeedHttp.class);
  UpstoxFeedService svc=new UpstoxFeedService(db,http,mock(VersionedVaultReader.class));
  try{
   when(db.update(anyString(),any(),any(),any(),any(),any())).thenReturn(1);
   when(db.update(anyString(),any(),any(),any(),any(),any(),any(),any())).thenReturn(1);
   when(http.get(contains("NSE.json.gz"),isNull(),anyInt())).thenReturn("[{\"instrument_key\":\"NSE_EQ|INE002A01018\",\"exchange\":\"NSE\",\"instrument_type\":\"EQ\",\"trading_symbol\":\"RELIANCE\",\"name\":\"Reliance Industries Limited\",\"isin\":\"INE002A01018\"}]".getBytes());
   when(http.get(contains("BSE.json.gz"),isNull(),anyInt())).thenReturn("[{\"instrument_key\":\"BSE_EQ|500325\",\"exchange\":\"BSE\",\"exchange_token\":\"500325\",\"instrument_type\":\"A\",\"trading_symbol\":\"RELIANCE\",\"name\":\"Reliance Industries Limited\",\"isin\":\"INE002A01018\"}]".getBytes());
   assertThat(svc.syncMaster()).isEqualTo(2);
   verify(db,times(2)).update(contains("upstox_instrument_map"),any(),any(),any(),any(),any(),any(),eq("UNKNOWN"));
  }catch(Exception e){throw new AssertionError(e);}
 }
 @Test void registryFailureCodesIdentifyVenueAndStageWithoutProviderPayload()throws Exception{
  JdbcTemplate db=mock(JdbcTemplate.class);FeedHttp http=mock(FeedHttp.class);
  var svc=new UpstoxFeedService(db,http,mock(VersionedVaultReader.class));
  String nse="{\"instrument_key\":\"NSE_EQ|INE002A01018\",\"exchange\":\"NSE\",\"instrument_type\":\"EQ\",\"trading_symbol\":\"RELIANCE\",\"isin\":\"INE002A01018\"}";
  String bse="{\"instrument_key\":\"BSE_EQ|500325\",\"exchange\":\"BSE\",\"exchange_token\":\"500325\",\"instrument_type\":\"A\",\"trading_symbol\":\"RELIANCE\",\"isin\":\"INE002A01018\"}";
  when(db.update(anyString(),any(),any(),any(),any(),any())).thenReturn(1);
  when(db.update(anyString(),any(),any(),any(),any(),any(),any(),any())).thenReturn(1);
  when(http.get(contains("NSE.json.gz"),isNull(),anyInt())).thenReturn(("["+nse+"]").getBytes());
  when(http.get(contains("BSE.json.gz"),isNull(),anyInt())).thenReturn(("["+bse+","+bse+"]").getBytes());
  assertThatThrownBy(svc::syncMaster).isInstanceOfSatisfying(UpstoxFeedService.MasterImportException.class,
    ex->assertThat(FeedRefreshScheduler.failureCode(ex)).isEqualTo("UPSTOX_BSE_MASTER_DUPLICATE_KEY"));
  when(http.get(contains("BSE.json.gz"),isNull(),anyInt())).thenReturn("[]".getBytes());
  assertThatThrownBy(svc::syncMaster).isInstanceOfSatisfying(UpstoxFeedService.MasterImportException.class,
    ex->assertThat(FeedRefreshScheduler.failureCode(ex)).isEqualTo("UPSTOX_BSE_MASTER_INVALID_ENVELOPE"));
  when(http.get(contains("BSE.json.gz"),isNull(),anyInt())).thenReturn(("[{"+ "\"private\":\"secret\"}]").getBytes());
  assertThatThrownBy(svc::syncMaster).isInstanceOfSatisfying(UpstoxFeedService.MasterImportException.class,
    ex->assertThat(FeedRefreshScheduler.failureCode(ex)).isEqualTo("UPSTOX_BSE_MASTER_NO_VALID_EQUITIES"));
  when(http.get(contains("BSE.json.gz"),isNull(),anyInt())).thenReturn( ("["+bse+"]").getBytes());
  when(db.update(contains("INSERT INTO instruments"),eq("BSE"),any(),any(),any(),any()))
    .thenThrow(new org.springframework.dao.DataIntegrityViolationException("private database detail"));
  assertThatThrownBy(svc::syncMaster).isInstanceOfSatisfying(UpstoxFeedService.MasterImportException.class,
    ex->{assertThat(FeedRefreshScheduler.failureCode(ex)).isEqualTo("UPSTOX_BSE_MASTER_REGISTRY_WRITE_FAILED");
         assertThat(ex.getMessage()).doesNotContain("private database detail");});
 }
 @Test void quoteUsesVaultTokenWithoutPersistingIt()throws Exception{
  JdbcTemplate db=mock(JdbcTemplate.class);FeedHttp http=mock(FeedHttp.class);VersionedVaultReader vault=mock(VersionedVaultReader.class);
  UUID user=UUID.randomUUID();when(vault.decrypt(user,"UPSTOX")).thenReturn("test-only-token");
  when(db.queryForObject(contains("upstox_instrument_map"),eq(Integer.class),any())).thenReturn(1);
  when(http.text(contains("market-quote/quotes"),eq("test-only-token"),anyInt())).thenReturn("{\"status\":\"success\",\"data\":{\"NSE_EQ:RELIANCE\":{\"last_price\":2500.50,\"instrument_token\":\"NSE_EQ|INE002A01018\",\"last_trade_time\":\"1760000000000\",\"timestamp\":\"2025-10-09T12:00:00Z\",\"prev_close_price\":2475.00}}}");
  JsonNode result=new UpstoxFeedService(db,http,vault).quote(user,"NSE_EQ|INE002A01018");
  assertThat(result.path("ltp").decimalValue()).isEqualByComparingTo(new BigDecimal("2500.50"));
  assertThat(result.path("previous_close").decimalValue()).isEqualByComparingTo(new BigDecimal("2475.00"));
  assertThat(result.path("as_of").asText()).isEqualTo(Instant.ofEpochMilli(1760000000000L).toString());
  assertThat(result.path("timestamp_basis").asText()).isEqualTo("LAST_TRADE_TIME");
  verify(db).update(contains("market_quotes"),any(),any(),any());
 }
 @Test void quoteRejectsWrongIdentityOrMissingTradeTime()throws Exception{
  JdbcTemplate db=mock(JdbcTemplate.class);FeedHttp http=mock(FeedHttp.class);VersionedVaultReader vault=mock(VersionedVaultReader.class);
  UUID user=UUID.randomUUID();when(vault.decrypt(user,"UPSTOX")).thenReturn("test-only");
  when(db.queryForObject(contains("upstox_instrument_map"),eq(Integer.class),any())).thenReturn(1);
  var service=new UpstoxFeedService(db,http,vault);
  for(String item:List.of(
     "{\"instrument_token\":\"NSE_EQ|INE000A01001\",\"last_price\":100}",
     "{\"instrument_token\":\"NSE_EQ|INE002A01018\",\"last_price\":100}")){
   when(http.text(contains("/v3/market-quote/quotes"),eq("test-only"),anyInt()))
     .thenReturn("{\"status\":\"success\",\"data\":{\"quote\":"+item+"}}");
   assertThatThrownBy(()->service.quote(user,"NSE_EQ|INE002A01018")).isInstanceOf(IllegalStateException.class);
  }
  verify(db,never()).update(contains("market_quotes"),any(),any(),any());
 }
 @Test void amfiParserAndHistoricalNavHttp()throws Exception{
  JdbcTemplate db=mock(JdbcTemplate.class);FeedHttp http=mock(FeedHttp.class);AmfiFeedService svc=new AmfiFeedService(db,http);
  when(db.update(contains("INSERT INTO mutual_fund_schemes"),any(),any(),any(),any(),any(),any(),any(),any(),any())).thenReturn(1);
  assertThat(svc.importNav("123456;INF000A01001;;Example Growth;123.45;13-Nov-2026")).isEqualTo(1);
  assertThat(svc.importNav("123457;INF000A01002;-;Example Fund;Direct Plan;Growth Option;125.50;23-Nov-2026")).isEqualTo(1);
  when(http.text(contains("api.mfapi.in/mf/123456"),isNull(),anyInt())).thenReturn("{\"meta\":{\"scheme_code\":123456},\"data\":[{\"date\":\"13-11-2026\",\"nav\":\"123.45\"}]}");
  assertThat(svc.history(123456)).isEqualTo(1);
  verify(db,atLeastOnce()).update(contains("mutual_fund_nav"),any(),any(),any());
 }
 @Test void scheduleSkipsPrePublicationAndWeekend(){
  JdbcTemplate db=mock(JdbcTemplate.class);MarketCalendarService cal=mock(MarketCalendarService.class);
  when(cal.isTradingDay(eq("NSE"),any())).thenAnswer(inv->{
   LocalDate d=inv.getArgument(1);
   return d.equals(LocalDate.of(2026,11,13));
  });
  FreshnessService svc=new FreshnessService(db,cal);
  Instant mondayDay=ZonedDateTime.of(2026,11,16,15,0,0,0,MarketCalendarService.IST).toInstant();
  assertThat(svc.expectedNavDate(mondayDay)).isEqualTo(LocalDate.of(2026,11,13));
  Instant mondayNight=ZonedDateTime.of(2026,11,16,22,5,0,0,MarketCalendarService.IST).toInstant();
  when(cal.isTradingDay("NSE",LocalDate.of(2026,11,16))).thenReturn(true);
  assertThat(svc.expectedNavDate(mondayNight)).isEqualTo(LocalDate.of(2026,11,16));
 }
}
