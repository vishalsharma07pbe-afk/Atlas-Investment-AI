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
}
