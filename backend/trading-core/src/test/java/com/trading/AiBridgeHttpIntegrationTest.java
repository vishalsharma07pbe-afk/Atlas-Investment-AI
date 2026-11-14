package com.trading;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties={
  "ALLOW_REGISTRATION=true",
  "ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
  "INTERNAL_SERVICE_TOKEN=bridge-integration-secret-at-least-32-chars",
  "atlas.ai.proxy-enabled=true",
  "atlas.ai.intelligence-url=http://127.0.0.1:18000"
})
@AutoConfigureMockMvc
class AiBridgeHttpIntegrationTest {
  static final PostgreSQLContainer<?> POSTGRES=new PostgreSQLContainer<>("postgres:16-alpine").withInitScript("test-schema.sql");
  static {if(System.getenv("TEST_DATABASE_URL")==null)POSTGRES.start();}
  @org.junit.jupiter.api.AfterAll static void stop(){if(POSTGRES.isRunning())POSTGRES.stop();}
  @DynamicPropertySource static void db(DynamicPropertyRegistry r){
    r.add("spring.datasource.url",()->System.getenv("TEST_DATABASE_URL")!=null?System.getenv("TEST_DATABASE_URL"):POSTGRES.getJdbcUrl());
    r.add("spring.datasource.username",()->System.getenv("TEST_DATABASE_URL")!=null?System.getenv("TEST_DATABASE_USERNAME"):POSTGRES.getUsername());
    r.add("spring.datasource.password",()->System.getenv("TEST_DATABASE_URL")!=null?System.getenv("TEST_DATABASE_PASSWORD"):POSTGRES.getPassword());
  }
  @Autowired MockMvc mvc;
  @Autowired JdbcTemplate jdbc;
  @Autowired ObjectMapper json;

  @Test void realPythonBoundaryEnforcesJwtAndSanitizesPayload() throws Exception {
    String email="bridge-"+UUID.randomUUID()+"@example.test";
    String creds=json.writeValueAsString(Map.of("email",email,"password","very-strong-password-123"));
    mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(creds)).andExpect(status().isOk());
    String login=mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(creds))
      .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    String token="Bearer "+json.readTree(login).path("access_token").asText();
    mvc.perform(get("/api/v1/ai/providers/health").header("Authorization",token)).andExpect(status().isOk());
    java.net.http.HttpClient http=java.net.http.HttpClient.newHttpClient();
    for(String candidate:List.of("","incorrect-service-token-with-length-40-xxxx")){
      java.net.http.HttpRequest request=java.net.http.HttpRequest.newBuilder(
        java.net.URI.create("http://127.0.0.1:18000/api/v1/ai/providers/health"))
        .header("X-Atlas-Service-Token",candidate).GET().build();
      int status=http.send(request,java.net.http.HttpResponse.BodyHandlers.discarding()).statusCode();
      assertThat(status).isIn(401,403);
    }
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",token)
      .contentType(MediaType.APPLICATION_JSON).content("""
      {"symbol":"TCS","assetType":"EQUITY","quantity":3,"averageCost":123456,"lastPrice":1000}
      """)).andExpect(status().isOk());
    mvc.perform(post("/api/v1/portfolio/holdings").header("Authorization",token)
      .contentType(MediaType.APPLICATION_JSON).content("""
      {"symbol":"INFY","assetType":"EQUITY","quantity":1,"averageCost":987654,"lastPrice":1000}
      """)).andExpect(status().isOk());
    String payload="""
      {"symbol":"TCS","market":"NSE","price_change_pct":2.0,"technical_summary":"Trend evidence only"}
      """;
    mvc.perform(post("/api/v1/ai/analyze/TCS").header("Authorization",token)
      .contentType(MediaType.APPLICATION_JSON).content(payload)).andExpect(status().isOk())
      .andExpect(jsonPath("$.symbol").value("TCS"));
    String recorded=Files.readString(Path.of(System.getenv("ATLAS_BRIDGE_CAPTURE_FILE")));
    JsonNode observed=json.readTree(recorded);
    assertThat(observed.path("technical_summary").asText()).contains("75.00%");
    for(String forbidden:List.of("123456","987654","quantity","average_cost","access_token","upstox","user_id","last_price"))
      assertThat(recorded.toLowerCase(Locale.ROOT)).doesNotContain(forbidden.toLowerCase(Locale.ROOT));
    mvc.perform(post("/api/v1/ai/analyze/TCS").header("Authorization",token)
      .contentType(MediaType.APPLICATION_JSON).content("""
        {"symbol":"TCS","quantity":100,"access_token":"secret"}
      """)).andExpect(status().isUnprocessableEntity());
    mvc.perform(post("/api/v1/auth/logout").header("Authorization",token)).andExpect(status().isOk());
    mvc.perform(post("/api/v1/ai/analyze/TCS").header("Authorization",token)
      .contentType(MediaType.APPLICATION_JSON).content(payload)).andExpect(status().isUnauthorized());
  }
}
