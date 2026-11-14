package com.trading;

import com.trading.api.AuthSecurity;
import java.util.UUID;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import org.springframework.http.MediaType;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;

@SpringBootTest(properties={"ALLOW_REGISTRATION=true","ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="})
@AutoConfigureMockMvc
class AuthIsolationIntegrationTest {
  @DynamicPropertySource static void db(DynamicPropertyRegistry registry){
    registry.add("spring.datasource.url",()->DataFoundationIntegrationTest.EXTERNAL_URL!=null?
      DataFoundationIntegrationTest.EXTERNAL_URL:DataFoundationIntegrationTest.POSTGRES.getJdbcUrl());
    registry.add("spring.datasource.username",()->DataFoundationIntegrationTest.EXTERNAL_URL!=null?
      System.getenv("TEST_DATABASE_USERNAME"):DataFoundationIntegrationTest.POSTGRES.getUsername());
    registry.add("spring.datasource.password",()->DataFoundationIntegrationTest.EXTERNAL_URL!=null?
      System.getenv("TEST_DATABASE_PASSWORD"):DataFoundationIntegrationTest.POSTGRES.getPassword());
  }
  @Autowired MockMvc mvc;
  @Autowired JdbcTemplate jdbc;
  @Autowired ObjectMapper mapper;
  String create(String email)throws Exception{
    String input=mapper.writeValueAsString(Map.of("email",email,"password","strong-password-12345"));
    mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk());
    String response=mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON).content(input))
      .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
    return "Bearer "+mapper.readTree(response).path("access_token").asText();
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
}
