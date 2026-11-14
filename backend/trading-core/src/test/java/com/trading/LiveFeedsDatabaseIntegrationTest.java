package com.trading;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import com.trading.api.*;
import com.trading.market.*;
import java.math.BigDecimal;
import java.sql.Date;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;

@SpringBootTest @AutoConfigureMockMvc(addFilters=false)
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
 @Autowired MockMvc mvc;
 @MockBean FeedHttp http;
 @MockBean VersionedVaultReader vault;
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
}
