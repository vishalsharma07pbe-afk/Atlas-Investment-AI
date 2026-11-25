package com.trading;

import com.trading.api.AuthSecurity;
import java.util.UUID;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.containers.PostgreSQLContainer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import org.springframework.http.MediaType;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import jakarta.servlet.http.Cookie;
import com.trading.market.UserAlertEvaluator;

@SpringBootTest(properties={"ALLOW_REGISTRATION=true","ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","atlas.market.freshness.enabled=false","atlas.alerts.scheduler.enabled=false"})
@AutoConfigureMockMvc
class AuthIsolationIntegrationTest {
  static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine").withInitScript("test-schema.sql");
  static {if(System.getenv("TEST_DATABASE_URL")==null)POSTGRES.start();}
  @org.junit.jupiter.api.AfterAll static void stop(){if(POSTGRES.isRunning())POSTGRES.stop();}
  @DynamicPropertySource static void db(DynamicPropertyRegistry registry){
    registry.add("spring.datasource.url",()->System.getenv("TEST_DATABASE_URL")!=null?
      System.getenv("TEST_DATABASE_URL"):POSTGRES.getJdbcUrl());
    registry.add("spring.datasource.username",()->System.getenv("TEST_DATABASE_URL")!=null?
      System.getenv("TEST_DATABASE_USERNAME"):POSTGRES.getUsername());
    registry.add("spring.datasource.password",()->System.getenv("TEST_DATABASE_URL")!=null?
      System.getenv("TEST_DATABASE_PASSWORD"):POSTGRES.getPassword());
  }
  @Autowired MockMvc mvc;
  @Autowired JdbcTemplate jdbc;
  @Autowired ObjectMapper mapper;
  @Autowired UserAlertEvaluator alertEvaluator;
  @Autowired com.trading.market.PortfolioRiskNotifications riskNotifications;
  String create(String email)throws Exception{
    String input=mapper.writeValueAsString(Map.of("email",email,"password","strong-password-12345"));
    mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk());
    String response=mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    return "Bearer "+mapper.readTree(response).path("access_token").asText();
  }
  @Test void priceAlertsAreDeliveredOnceAndRemainUserScoped()throws Exception{
    String email="alerts-"+UUID.randomUUID()+"@example.test";
    String authorization=create(email);
    UUID user=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    jdbc.update("INSERT INTO upstox_instrument_map(instrument_key,exchange_code,trading_symbol,instrument_type) VALUES ('NSE_EQ|ALERT','NSE','ALERT','EQ')");
    jdbc.update("INSERT INTO upstox_market_quotes(instrument_key,ltp,source_code,quoted_at) VALUES ('NSE_EQ|ALERT',125,'UPSTOX',now())");
    jdbc.update("INSERT INTO user_alert_rules(user_id,name,alert_type,target_identifier,condition) VALUES (?,?, 'PRICE','ALERT',?::jsonb)",user,"Price crossed","{\"operator\":\"AT_OR_ABOVE\",\"value\":120}");
    org.junit.jupiter.api.Assertions.assertEquals(1,alertEvaluator.evaluate());
    org.junit.jupiter.api.Assertions.assertEquals(0,alertEvaluator.evaluate());
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",authorization))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1))
      .andExpect(jsonPath("$[0].delivery_status").value("DELIVERED"));
  }
  @Test void anonymousAndCrossUserIsolation()throws Exception{
    mvc.perform(get("/api/v1/portfolio/holdings")).andExpect(status().isUnauthorized());
    mvc.perform(get("/api/v1/ai/providers/health")).andExpect(status().isUnauthorized());
    String a=create("a-"+UUID.randomUUID()+"@example.test");
    String b=create("b-"+UUID.randomUUID()+"@example.test");
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content(
        "{\"symbol\":\"TCS\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/holdings").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    mvc.perform(get("/api/v1/portfolio/holdings").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
  }
  @Test void browserCookieRestoresSessionAndLogoutClearsIt()throws Exception{
    String input=mapper.writeValueAsString(Map.of("email","cookie-"+UUID.randomUUID()+"@example.test","password","strong-password-12345"));
    mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(input)).andExpect(status().isOk());
    MockHttpServletResponse login=mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk()).andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("ATLAS_SESSION=")))
      .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("HttpOnly")))
      .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("Path=/")))
      .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("Max-Age=604800")))
      .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("SameSite=Strict"))).andReturn().getResponse();
    Cookie cookie=login.getCookie("ATLAS_SESSION");
    mvc.perform(get("/api/v1/auth/me").cookie(cookie)).andExpect(status().isOk());
    mvc.perform(post("/api/v1/portfolio/holdings").cookie(cookie)
      .header("Origin","https://attacker.example").header("Sec-Fetch-Site","cross-site")
      .contentType(MediaType.APPLICATION_JSON).content(
        "{\"symbol\":\"TCS\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isForbidden());
    mvc.perform(post("/api/v1/auth/logout").cookie(cookie).header("Origin","http://localhost"))
      .andExpect(status().isOk())
      .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.containsString("Max-Age=0")));
  }
  @Test void logoutRevokesUntilExpiryAndIndependentLoginRemainsValid()throws Exception{
    String email="revoke-"+UUID.randomUUID()+"@example.test";
    String first=create(email);
    String input=mapper.writeValueAsString(Map.of("email",email,"password","strong-password-12345"));
    String second="Bearer "+mapper.readTree(mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("access_token").asText();
    org.junit.jupiter.api.Assertions.assertNotEquals(first,second);
    mvc.perform(post("/api/v1/auth/logout").header("Authorization",first)).andExpect(status().isOk());
    UUID user=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM revoked_jwt WHERE user_id=? AND expires_at>now()+interval '6 days'",Integer.class,user));
    mvc.perform(get("/api/v1/auth/me").header("Authorization",first)).andExpect(status().isUnauthorized());
    mvc.perform(get("/api/v1/auth/me").header("Authorization",second)).andExpect(status().isOk());
  }
  @Test void researchWorkspaceStateIsPersistedAndUserScoped()throws Exception{
    String a=create("research-a-"+UUID.randomUUID()+"@example.test");
    String b=create("research-b-"+UUID.randomUUID()+"@example.test");
    jdbc.update("INSERT INTO instruments(exchange_id,symbol,series,source) VALUES ((SELECT id FROM exchanges WHERE code='NSE'),'WORKSPACE','EQ','TEST') ON CONFLICT DO NOTHING");
    long instrument=jdbc.queryForObject("SELECT id FROM instruments WHERE symbol='WORKSPACE'",Long.class);

    String saved=mvc.perform(post("/api/v1/research-workspace/screeners").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"Quality\",\"definition\":{\"maxPe\":25}}"))
      .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    String screenerId=mapper.readTree(saved).path("id").asText();
    mvc.perform(get("/api/v1/research-workspace/screeners").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
    mvc.perform(get("/api/v1/research-workspace/screeners").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    mvc.perform(delete("/api/v1/research-workspace/screeners/{id}",screenerId).header("Authorization",b))
      .andExpect(status().isNotFound());

    mvc.perform(put("/api/v1/research-workspace/watchlist/{id}",instrument).header("Authorization",a))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/research-workspace/watchlist").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$[0].symbol").value("WORKSPACE"));
    mvc.perform(get("/api/v1/research-workspace/watchlist").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));

    mvc.perform(post("/api/v1/research-workspace/alerts").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"Price watch\",\"alertType\":\"PRICE\",\"targetIdentifier\":\"NSE:WORKSPACE\",\"condition\":{\"operator\":\"GTE\",\"value\":100}}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/research-workspace/alerts").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
  }
  @Test void recordedValuationAgeAndPerformanceAreOwnerScoped()throws Exception{
    String email="valuation-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("valuation-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    for(String symbol:new String[]{"RECENTVAL","STALEVAL","UNDATEDVAL","FUTUREVAL","UNPRICEDVAL"}){
      mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
        .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(Map.of(
          "symbol",symbol,"assetType","EQUITY","quantity",2,"averageCost",100,"lastPrice",125))))
        .andExpect(status().isOk());
    }
    jdbc.update("UPDATE personal_holdings SET price_as_of=now()-interval '10 days' WHERE user_id=? AND symbol='STALEVAL'",owner);
    jdbc.update("UPDATE personal_holdings SET price_as_of=NULL WHERE user_id=? AND symbol='UNDATEDVAL'",owner);
    jdbc.update("UPDATE personal_holdings SET price_as_of=now()+interval '1 day' WHERE user_id=? AND symbol='FUTUREVAL'",owner);
    jdbc.update("UPDATE personal_holdings SET last_price=NULL,price_as_of=NULL WHERE user_id=? AND symbol='UNPRICEDVAL'",owner);
    mvc.perform(get("/api/v1/portfolio/analysis").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.holdingCount").value(5))
      .andExpect(jsonPath("$.pricedMarketValue").value(1000))
      .andExpect(jsonPath("$.pricedCostBasis").value(800))
      .andExpect(jsonPath("$.recordedReturnPercent").value(25.0))
      .andExpect(jsonPath("$.recentRecordedHoldings").value(1))
      .andExpect(jsonPath("$.stalePriceHoldings").value(1))
      .andExpect(jsonPath("$.undatedPriceHoldings").value(1))
      .andExpect(jsonPath("$.futureDatedPriceHoldings").value(1))
      .andExpect(jsonPath("$.unpricedHoldings").value(1))
      .andExpect(jsonPath("$.valuationFreshnessStatus").value("INCOMPLETE_OR_AGED"));
    mvc.perform(get("/api/v1/portfolio/analysis").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.holdingCount").value(0))
      .andExpect(jsonPath("$.valuationFreshnessStatus").value("NO_HOLDINGS"))
      .andExpect(jsonPath("$.recordedReturnPercent").isEmpty());
    jdbc.update("UPDATE personal_holdings SET previous_close=120 WHERE user_id=? AND symbol='RECENTVAL'",owner);
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"RECENTVAL\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100,\"lastPrice\":130}"))
      .andExpect(status().isOk());
    org.junit.jupiter.api.Assertions.assertNull(jdbc.queryForObject("SELECT previous_close FROM personal_holdings WHERE user_id=? AND symbol='RECENTVAL'",java.math.BigDecimal.class,owner));
  }

  @Test void portfolioHistoryCalculatesOnlyFromDatedUserEvidence()throws Exception{
    String email="history-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("history-b-"+UUID.randomUUID()+"@example.test");
    UUID user=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    LocalDate today=LocalDate.now(),start=today.minusYears(1),middle=today.minusMonths(6);
    mvc.perform(post("/api/v1/portfolio/history/transactions").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(Map.of(
        "symbol","CASH","assetType","CASH","transactionType","DEPOSIT",
        "transactionDate",start.toString(),"cashAmount",1000))))
      .andExpect(status().isOk());
    jdbc.update("INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions) VALUES (?,?,1000,1,0),(?,?,900,1,0),(?,?,1100,1,0)",user,start,user,middle,user,today);

    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.xirr_status").value("AVAILABLE"))
      .andExpect(jsonPath("$.xirr_percent").value(org.hamcrest.Matchers.closeTo(10.0,0.2)))
      .andExpect(jsonPath("$.maximum_drawdown_percent").value(-10.0));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.transaction_count").value(0))
      .andExpect(jsonPath("$.xirr_status").value("UNAVAILABLE_REQUIRES_EXTERNAL_CASH_FLOWS_AND_VALUATION"));
  }

  @Test void historicalPerformanceRejectsPartialValuationsAndSeparatesCashFlows()throws Exception{
    String email="performance-integrity-"+UUID.randomUUID()+"@example.test";
    String a=create(email);
    UUID user=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    LocalDate today=LocalDate.now(com.trading.market.MarketCalendarService.IST);
    LocalDate start=today.minusDays(370),terminal=today.minusDays(5);
    for(var flow:java.util.List.of(
        Map.of("transactionDate",start.toString(),"transactionType","DEPOSIT","cashAmount",1000),
        Map.of("transactionDate",today.toString(),"transactionType","DEPOSIT","cashAmount",500))){
      var input=new java.util.HashMap<String,Object>(flow);
      input.put("symbol","CASH");input.put("assetType","CASH");
      mvc.perform(post("/api/v1/portfolio/history/transactions").header("Authorization",a)
        .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(input))).andExpect(status().isOk());
    }
    jdbc.update("INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions) VALUES (?,?,1000,1,0),(?,?,1100,1,0),(?,?,2000,1,0)",user,start,user,terminal,user,today.plusDays(1));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.xirr_percent").value(org.hamcrest.Matchers.closeTo(10.0,0.1)))
      .andExpect(jsonPath("$.valuation_through").value(terminal.toString()))
      .andExpect(jsonPath("$.external_flows_after_valuation").value(1))
      .andExpect(jsonPath("$.future_snapshot_count").value(1));
    mvc.perform(post("/api/v1/portfolio/history/transactions").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(Map.of(
        "symbol","CASH","assetType","CASH","transactionType","WITHDRAWAL",
        "transactionDate",start.plusDays(30).toString(),"cashAmount",50)))).andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.drawdown_status").value("UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY"));
    mvc.perform(post("/api/v1/portfolio/history/transactions").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(Map.of(
        "symbol","CASH","assetType","CASH","transactionType","DEPOSIT",
        "transactionDate",start.plusDays(60).toString(),"cashAmount",50)))).andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.xirr_status").value("UNAVAILABLE_AMBIGUOUS_OR_UNSUPPORTED_CASH_FLOWS"));
    jdbc.update("UPDATE portfolio_valuation_snapshots SET unpriced_positions=1 WHERE user_id=? AND valuation_date=?",user,terminal);
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.xirr_status").value("UNAVAILABLE_INCOMPLETE_TERMINAL_VALUATION"))
      .andExpect(jsonPath("$.drawdown_status").value("UNAVAILABLE_INCOMPLETE_VALUATION_HISTORY"));
  }

  @Test void rollingPortfolioEstimatesAreOwnerScopedAndIndependentOfOldGaps()throws Exception{
    String email="rolling-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("rolling-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    LocalDate end=LocalDate.now(com.trading.market.MarketCalendarService.IST).minusDays(1);
    for(int i=0;i<=30;i++){
      jdbc.update("INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions) VALUES (?,?,?,1,0)",owner,end.minusDays(30-i),i==30?1100:1000);
    }
    jdbc.update("INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions) VALUES (?,?,1000,1,0)",owner,end.minusDays(100));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.flow_adjusted_status").value("UNAVAILABLE_VALUATION_GAPS"))
      .andExpect(jsonPath("$.rolling_performance[0].days").value(30))
      .andExpect(jsonPath("$.rolling_performance[0].status").value("AVAILABLE_ESTIMATE"))
      .andExpect(jsonPath("$.rolling_performance[0].returnPercent").value(org.hamcrest.Matchers.closeTo(10.0,0.001)))
      .andExpect(jsonPath("$.rolling_performance[1].status").value("UNAVAILABLE_EXACT_START_DATE"))
      .andExpect(jsonPath("$.weekly_risk_estimate.status").value("UNAVAILABLE_EXACT_WEEKLY_HISTORY"))
      .andExpect(jsonPath("$.benchmark_risk_estimate.attentionStatus").value("INSUFFICIENT_EVIDENCE"));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.rolling_performance[0].status").value("UNAVAILABLE_REQUIRES_TWO_VALUATIONS"))
      .andExpect(jsonPath("$.rolling_performance[0].returnPercent").isEmpty());
  }

  @Test void linkedDietzSeparatesRecordedCapitalFlowsFromPerformance()throws Exception{
    String email="dietz-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("dietz-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    LocalDate today=LocalDate.now(com.trading.market.MarketCalendarService.IST);
    LocalDate start=today.minusDays(3),middle=today.minusDays(2),end=today.minusDays(1);
    jdbc.update("INSERT INTO portfolio_valuation_snapshots(user_id,valuation_date,total_value,priced_positions,unpriced_positions) VALUES (?,?,1000,1,0),(?,?,1500,1,0),(?,?,1350,1,0)",owner,start,owner,middle,owner,end);
    mvc.perform(post("/api/v1/portfolio/history/transactions").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(Map.of(
        "symbol","CASH","assetType","CASH","transactionType","DEPOSIT",
        "transactionDate",middle.toString(),"cashAmount",500)))).andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.flow_adjusted_status").value("AVAILABLE_ESTIMATE"))
      .andExpect(jsonPath("$.flow_adjusted_return_percent").value(-10.0))
      .andExpect(jsonPath("$.flow_adjusted_drawdown_percent").value(-10.0))
      .andExpect(jsonPath("$.flow_adjusted_cash_flow_count").value(1))
      .andExpect(jsonPath("$.flow_adjusted_through").value(end.toString()))
      .andExpect(jsonPath("$.drawdown_status").value("UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY"));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.flow_adjusted_status").value("UNAVAILABLE_REQUIRES_TWO_VALUATIONS"))
      .andExpect(jsonPath("$.flow_adjusted_return_percent").isEmpty());
  }

  @Test void automaticValuationsAreOwnerScopedIdempotentAndDoNotOverwriteManualRecords()throws Exception{
    String suffix=UUID.randomUUID().toString();
    String email="auto-value-"+suffix+"@example.test",other="auto-manual-"+suffix+"@example.test",aged="auto-aged-"+suffix+"@example.test";
    String a=create(email),b=create(other),c=create(aged);
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    UUID manual=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,other);
    UUID stale=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,aged);
    for(String token:new String[]{a,b,c}){
      mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",token)
        .contentType(MediaType.APPLICATION_JSON)
        .content("{\"symbol\":\"AUTOSNAP\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100,\"lastPrice\":125}"))
        .andExpect(status().isOk());
    }
    mvc.perform(post("/api/v1/portfolio/history/snapshots/current").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.recorded").value(true));
    jdbc.update("UPDATE personal_holdings SET last_price=999 WHERE user_id=?",manual);
    jdbc.update("UPDATE personal_holdings SET price_as_of=now()-interval '10 days' WHERE user_id=?",stale);
    var service=new com.trading.market.PortfolioValuationHistoryService(jdbc);
    for(int i=0;i<30;i++){if(service.captureDue(5)==0)break;}
    LocalDate today=LocalDate.now(com.trading.market.MarketCalendarService.IST);
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.automatic_snapshot_count").value(1))
      .andExpect(jsonPath("$.latest_capture_source").value("AUTO_RECORDED"))
      .andExpect(jsonPath("$.latest_oldest_price_at").isNotEmpty());
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.automatic_snapshot_count").value(0))
      .andExpect(jsonPath("$.latest_capture_source").value("MANUAL_RECORDED"));
    mvc.perform(get("/api/v1/portfolio/history/performance").header("Authorization",c))
      .andExpect(status().isOk()).andExpect(jsonPath("$.snapshot_count").value(0));
    jdbc.update("UPDATE personal_holdings SET last_price=900 WHERE user_id=?",owner);
    service.captureDue(5);
    for(UUID user:new UUID[]{owner,manual}){
      org.junit.jupiter.api.Assertions.assertEquals(0,new java.math.BigDecimal("250").compareTo(
        jdbc.queryForObject("SELECT total_value FROM portfolio_valuation_snapshots WHERE user_id=? AND valuation_date=?",java.math.BigDecimal.class,user,today)));
      org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject(
        "SELECT count(*) FROM portfolio_valuation_snapshots WHERE user_id=? AND valuation_date=?",Integer.class,user,today));
    }
  }

  @Test void agedHoldingsCannotReplaceRecordedValuation()throws Exception{
    String email="snapshot-integrity-"+UUID.randomUUID()+"@example.test";
    String a=create(email);
    UUID user=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    LocalDate today=LocalDate.now(com.trading.market.MarketCalendarService.IST);
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"SNAPTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100,\"lastPrice\":125}")).andExpect(status().isOk());
    mvc.perform(post("/api/v1/portfolio/history/snapshots/current").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.recorded").value(true));
    jdbc.update("UPDATE personal_holdings SET price_as_of=now()-interval '10 days',last_price=999 WHERE user_id=?",user);
    mvc.perform(post("/api/v1/portfolio/history/snapshots/current").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.recorded").value(false));
    org.junit.jupiter.api.Assertions.assertEquals(0,new java.math.BigDecimal("250").compareTo(
      jdbc.queryForObject("SELECT total_value FROM portfolio_valuation_snapshots WHERE user_id=? AND valuation_date=?",java.math.BigDecimal.class,user,today)));
  }

  @Test void automaticPortfolioReviewIsOwnerScopedAndUpdatesAfterDeletion()throws Exception{
    String a=create("doctor-a-"+UUID.randomUUID()+"@example.test");
    String b=create("doctor-b-"+UUID.randomUUID()+"@example.test");
    mvc.perform(get("/api/v1/portfolio/review")).andExpect(status().isUnauthorized());
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"DOCTORTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100,\"lastPrice\":80}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.holding_count").value(1))
      .andExpect(jsonPath("$.holdings[0].symbol").value("DOCTORTEST"))
      .andExpect(jsonPath("$.thesis_monitor_version").value("ANNUAL_DIRECTION_V1"))
      .andExpect(jsonPath("$.fund_thesis_changed_count").value(0))
      .andExpect(jsonPath("$.fund_thesis_attention_count").value(0))
      .andExpect(jsonPath("$.diversification.allocation_research.status").value("INSUFFICIENT_RECENT_EXACT_VALUATIONS"))
      .andExpect(jsonPath("$.diversification.exposure_stress.status").value("INSUFFICIENT_RECENT_VALUATIONS"))
      .andExpect(jsonPath("$.holdings[0].thesis_monitor_status").value("NO_CURRENT_DATED_TRENDS"))
      .andExpect(jsonPath("$.attention_count").value(1));
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.holding_count").value(0));
    long id=jdbc.queryForObject("SELECT id FROM personal_holdings WHERE symbol='DOCTORTEST'",Long.class);
    mvc.perform(delete("/api/v1/portfolio/holdings/"+id).header("Authorization",a)).andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.holding_count").value(0));
  }


  @Test void portfolioDigestIsDeduplicatedAndOwnerScoped()throws Exception{
    String a=create("digest-a-"+UUID.randomUUID()+"@example.test");
    String b=create("digest-b-"+UUID.randomUUID()+"@example.test");
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"DIGESTTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100,\"lastPrice\":80}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a)).andExpect(status().isOk());
    riskNotifications.evaluate();riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications/summary").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.unread_count").value(1));
    mvc.perform(get("/api/v1/research-workspace/notifications/summary").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.unread_count").value(0));
    String result=mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1))
      .andExpect(jsonPath("$[0].event_type").value("PORTFOLIO_RISK")).andReturn().getResponse().getContentAsString();
    String id=mapper.readTree(result).get(0).path("id").asText();
    mvc.perform(patch("/api/v1/research-workspace/notifications/"+id+"/read").header("Authorization",b)).andExpect(status().isNotFound());
    mvc.perform(patch("/api/v1/research-workspace/notifications/"+id+"/read").header("Authorization",a)).andExpect(status().isOk());
    riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications/summary").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.unread_count").value(0));
  }

  @Test void quarterlyOwnershipAlertIsDeduplicatedAndOwnerScoped()throws Exception{
    String email="ownership-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("ownership-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"OWNTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a)).andExpect(status().isOk());
    long holding=jdbc.queryForObject("SELECT id FROM personal_holdings WHERE user_id=? AND symbol='OWNTEST'",Long.class,owner);
    var change=Map.of("category","promoters","currentDate","2026-09-30","attention","REVIEW");
    var item=Map.of("id",holding,"symbol","OWNTEST","asset_type","EQUITY","isin","INE002A01018","exchange","NSE",
      "ownership_changes",java.util.List.of(change));
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now(),result=jsonb_set(result,'{holdings}',?::jsonb) WHERE user_id=?",
      mapper.writeValueAsString(java.util.List.of(item)),owner);
    riskNotifications.evaluate();riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1))
      .andExpect(jsonPath("$[0].title").value("Quarterly ownership review"));
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    mvc.perform(delete("/api/v1/portfolio/holdings/"+holding).header("Authorization",a)).andExpect(status().isOk());
    riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
  }

  @Test void thesisAlertsAreSelectiveDeduplicatedAndOwnerScoped()throws Exception{
    String email="thesis-alert-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("thesis-alert-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"THESISTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isOk());
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"118955\",\"assetType\":\"MUTUAL_FUND\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a)).andExpect(status().isOk());
    long equity=jdbc.queryForObject("SELECT id FROM personal_holdings WHERE user_id=? AND symbol='THESISTEST'",Long.class,owner);
    long fund=jdbc.queryForObject("SELECT id FROM personal_holdings WHERE user_id=? AND symbol='118955'",Long.class,owner);
    var decline=Map.of("metric","NET_PROFIT","previous_period","March 2025","current_period","March 2026",
      "previous_direction","IMPROVING","current_direction","DECLINING");
    var improve=Map.of("metric","REVENUE","previous_period","March 2025","current_period","March 2026",
      "previous_direction","DECLINING","current_direction","IMPROVING");
    var expense=Map.of("metric","TER","previousDate","2026-11-24","currentDate","2026-11-25","attention","REVIEW");
    var lowerRisk=Map.of("metric","RISKOMETER","previousDate","2026-11-24","currentDate","2026-11-25","attention","OBSERVE");
    var equityRow=new java.util.LinkedHashMap<String,Object>(Map.of("id",equity,"symbol","THESISTEST","asset_type","EQUITY",
      "exchange","NSE","isin","INE002A01018","thesis_changes",java.util.List.of(decline,improve)));
    var fundRow=Map.of("id",fund,"symbol","118955","asset_type","MUTUAL_FUND","exact_scheme_code",118955,
      "fund_monitor_identity","118955:INF179K01BB2:DIRECT:TIGZIG_AMFI_DERIVED","fund_thesis_changes",java.util.List.of(expense,lowerRisk));
    String payload=mapper.writeValueAsString(java.util.List.of(equityRow,fundRow));
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now()-interval '6 minutes',result=jsonb_set(result,'{holdings}',?::jsonb) WHERE user_id=?",payload,owner);
    riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now() WHERE user_id=?",owner);
    riskNotifications.evaluate();riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(2));
    org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM user_notification_history WHERE user_id=? AND title='Financial thesis review'",Integer.class,owner));
    org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM user_notification_history WHERE user_id=? AND title='Fund disclosure review'",Integer.class,owner));
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    // A new metric on an obsolete holding revision must never be delivered.
    equityRow.put("thesis_changes",java.util.List.of(Map.of("metric","OPERATING_CASH_FLOW","previous_period","March 2025",
      "current_period","March 2026","previous_direction","IMPROVING","current_direction","NEGATIVE")));
    mvc.perform(delete("/api/v1/portfolio/holdings/"+equity).header("Authorization",a)).andExpect(status().isOk());
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now(),result=jsonb_set(result,'{holdings}',?::jsonb) WHERE user_id=?",
      mapper.writeValueAsString(java.util.List.of(equityRow,fundRow)),owner);
    riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(2));
  }

  @Test void portfolioLevelRiskAlertsAreWeeklyDeduplicatedAndOwnerScoped()throws Exception{
    String email="level-risk-"+UUID.randomUUID()+"@example.test";
    String a=create(email),b=create("level-risk-other-"+UUID.randomUUID()+"@example.test");
    UUID owner=jdbc.queryForObject("SELECT id FROM atlas_users WHERE email=?",UUID.class,email);
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",a)
      .contentType(MediaType.APPLICATION_JSON).content("{\"symbol\":\"LEVELTEST\",\"assetType\":\"EQUITY\",\"quantity\":2,\"averageCost\":100}"))
      .andExpect(status().isOk());
    mvc.perform(get("/api/v1/portfolio/review").header("Authorization",a)).andExpect(status().isOk());
    String day=LocalDate.now(com.trading.market.MarketCalendarService.IST).toString();
    var benchmark=Map.of("kind","BENCHMARK_RELATIVE_LAG","label","13-week lag","value",-6,"threshold",-5,"unit","PP","evidenceThrough",day);
    var concentration=Map.of("kind","TOP_THREE","label","Top three","value",80,"threshold",60,"unit","PERCENT","evidenceThrough",day);
    var risk=Map.of("benchmark_status","COMPARABLE_PRICE_REFERENCE","concentration_status","RECENT_RECORDED_EXPOSURES",
      "attention",java.util.List.of(benchmark,concentration));
    String payload=mapper.writeValueAsString(risk);
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now()-interval '6 minutes',result=jsonb_set(result,'{portfolio_level_risk}',?::jsonb) WHERE user_id=?",payload,owner);
    riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
    jdbc.update("UPDATE portfolio_review_snapshots SET generated_at=now() WHERE user_id=?",owner);
    riskNotifications.evaluate();riskNotifications.evaluate();
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",a))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(2));
    org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM user_notification_history WHERE user_id=? AND title='Benchmark underperformance review'",Integer.class,owner));
    org.junit.jupiter.api.Assertions.assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM user_notification_history WHERE user_id=? AND title='Portfolio concentration review'",Integer.class,owner));
    mvc.perform(get("/api/v1/research-workspace/notifications").header("Authorization",b))
      .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(0));
  }

}
