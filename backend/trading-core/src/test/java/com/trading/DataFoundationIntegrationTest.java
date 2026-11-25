package com.trading;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"ATLAS_JWT_SECRET=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","atlas.market.freshness.enabled=false","atlas.alerts.scheduler.enabled=false"})
@AutoConfigureMockMvc(addFilters=false)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class DataFoundationIntegrationTest {
  static final String EXTERNAL_URL=System.getenv("TEST_DATABASE_URL");
  static final PostgreSQLContainer<?> POSTGRES;
  static { POSTGRES=EXTERNAL_URL==null?new PostgreSQLContainer<>("postgres:16-alpine").withInitScript("test-schema.sql"):null; if(POSTGRES!=null)POSTGRES.start(); }
  @AfterAll static void stopContainer(){if(POSTGRES!=null)POSTGRES.stop();}
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry){
    registry.add("spring.datasource.url",()->EXTERNAL_URL!=null?EXTERNAL_URL:POSTGRES.getJdbcUrl());
    registry.add("spring.datasource.username",()->EXTERNAL_URL!=null?env("TEST_DATABASE_USERNAME","POSTGRES_USER"):POSTGRES.getUsername());
    registry.add("spring.datasource.password",()->EXTERNAL_URL!=null?env("TEST_DATABASE_PASSWORD","POSTGRES_PASSWORD"):POSTGRES.getPassword());
  }
  private static String env(String preferred,String fallback){String value=System.getenv(preferred);return value!=null?value:System.getenv(fallback);}
  @Autowired MockMvc mvc; @Autowired JdbcTemplate jdbc;

  @Test @Order(1) void registrySessionsAndCandlesAreValidatedAndReported() throws Exception {
    upload("instruments","instruments.csv","""
      exchange,symbol,series,isin,instrument_type,exchange_token,listing_status,listed_on,delisted_on,source_revision
      NSE,RELIANCE,EQ,INE002A01018,EQUITY,2885,ACTIVE,1977-11-23,,test-registry-1
      """).andExpect(status().isOk()).andExpect(jsonPath("$.recordsWritten").value(1));
    upload("market-sessions","sessions.csv","""
      exchange,session_date,session_type,is_trading_day,open_time,close_time,source_revision
      NSE,2026-11-10,REGULAR,true,2026-11-10T09:15:00+05:30,2026-11-10T15:30:00+05:30,test-calendar-1
      NSE,2026-11-11,REGULAR,true,2026-11-11T09:15:00+05:30,2026-11-11T15:30:00+05:30,test-calendar-1
      """).andExpect(status().isOk());
    upload("daily-candles","candles.csv","""
      exchange,symbol,series,trade_date,open,high,low,close,volume,adjustment_status,source_revision
      NSE,RELIANCE,EQ,2026-11-10,100,105,98,103,1000,RAW_UNADJUSTED,test-eod-1
      NSE,RELIANCE,EQ,2026-11-11,103,142,102,140,1100,RAW_UNADJUSTED,test-eod-1
      """).andExpect(status().isOk()).andExpect(jsonPath("$.recordsSeen").value(2));
    assertThat(jdbc.queryForObject("select count(*) from instruments",Long.class)).isEqualTo(1);
    mvc.perform(get("/api/v1/instruments").param("q","REL")).andExpect(status().isOk()).andExpect(jsonPath("$[0].symbol").value("RELIANCE"));
    mvc.perform(get("/api/v1/instruments").param("q","REL").param("exchange","nse")).andExpect(status().isOk()).andExpect(jsonPath("$[0].exchange").value("NSE"));
    assertThat(jdbc.queryForObject("select count(*) from market_candles",Long.class)).isEqualTo(2);
    assertThat(jdbc.queryForObject("select count(*) from data_quality_events where event_type='SUSPICIOUS_PRICE_DISCONTINUITY'",Long.class)).isEqualTo(1);
    mvc.perform(get("/api/v1/data-health/summary")).andExpect(status().isOk()).andExpect(jsonPath("$.instrumentCount").value(1)).andExpect(jsonPath("$.candleCount").value(2)).andExpect(jsonPath("$.providerMode").value("MANUAL_OR_NOT_YET_SYNCED"))
      .andExpect(jsonPath("$.liveMarketDataConnected").value(false))
      .andExpect(jsonPath("$.liveConnectionScope").value("NOT_OBSERVED_BY_BACKEND"))
      .andExpect(jsonPath("$.upstoxRegistry.records").value(0))
      .andExpect(jsonPath("$.upstoxDailyHistory.records").value(0))
      .andExpect(jsonPath("$.officialAmfiNav.records").value(0));
    mvc.perform(get("/api/v1/market-data/instruments/1/candles")).andExpect(status().isOk()).andExpect(jsonPath("$.timeframe").value("1d")).andExpect(jsonPath("$.count").value(2)).andExpect(jsonPath("$.candles[0].adjustment_status").value("RAW_UNADJUSTED"));
  }

  @Test @Order(2) void identicalArtifactIsIdempotent() throws Exception {
    String csv="""
      exchange,symbol,series,trade_date,open,high,low,close,volume,adjustment_status,source_revision
      NSE,RELIANCE,EQ,2026-11-10,100,105,98,103,1000,RAW_UNADJUSTED,test-eod-1
      NSE,RELIANCE,EQ,2026-11-11,103,142,102,140,1100,RAW_UNADJUSTED,test-eod-1
      """;
    upload("daily-candles","candles.csv",csv).andExpect(status().isOk()).andExpect(jsonPath("$.status").value("DUPLICATE"));
    assertThat(jdbc.queryForObject("select count(*) from market_candles",Long.class)).isEqualTo(2);
    assertThat(jdbc.queryForObject("select count(*) from ingestion_runs where status='DUPLICATE'",Long.class)).isEqualTo(1);
  }

  @Test @Order(3) void badOhlcRejectsWholeFileAndRecordsFailure() throws Exception {
    upload("daily-candles","bad.csv","""
      exchange,symbol,series,trade_date,open,high,low,close,volume,adjustment_status,source_revision
      NSE,RELIANCE,EQ,2026-11-10,100,99,98,103,1000,RAW_UNADJUSTED,bad-1
      """).andExpect(status().isBadRequest()).andExpect(jsonPath("$.status").value("REJECTED"));
    assertThat(jdbc.queryForObject("select count(*) from market_candles",Long.class)).isEqualTo(2);
    assertThat(jdbc.queryForObject("select count(*) from ingestion_runs where status='FAILED'",Long.class)).isEqualTo(1);
    assertThat(jdbc.queryForObject("select count(*) from data_quality_events where event_type='FILE_REJECTED'",Long.class)).isEqualTo(1);
  }

  @Test @Order(4) void explicitCorporateActionMultiplierRequiresExactIdentityAndPreservesRawPrices()throws Exception{
    String header="exchange,symbol,series,isin,action_type,ex_date,ratio,cash_amount,source_revision,ratio_basis\n";
    upload("corporate-actions","split.csv",header+"NSE,RELIANCE,EQ,INE002A01018,SPLIT,2026-11-11,2,,split-revision-1,POST_SHARES_PER_PRE_SHARE\n")
      .andExpect(status().isOk()).andExpect(jsonPath("$.recordsWritten").value(1));
    assertThat(jdbc.queryForObject("SELECT raw_payload->>'ratio_basis' FROM corporate_actions WHERE source_revision='split-revision-1'",String.class)).isEqualTo("POST_SHARES_PER_PRE_SHARE");
    upload("corporate-actions","bad-identity.csv",header+"NSE,RELIANCE,EQ,INE000A01001,SPLIT,2026-11-11,2,,bad-split-1,POST_SHARES_PER_PRE_SHARE\n")
      .andExpect(status().isBadRequest());
    upload("corporate-actions","bad-bonus.csv",header+"NSE,RELIANCE,EQ,INE002A01018,BONUS,2026-11-11,1,,bad-bonus-1,POST_SHARES_PER_PRE_SHARE\n")
      .andExpect(status().isBadRequest());
    upload("corporate-actions","legacy.csv","exchange,symbol,series,action_type,ex_date,ratio,cash_amount,source_revision\nNSE,RELIANCE,EQ,BONUS,2026-11-11,1,,legacy-action-1\n")
      .andExpect(status().isOk());
    assertThat(jdbc.queryForObject("SELECT raw_payload->>'ratio_basis' FROM corporate_actions WHERE source_revision='legacy-action-1'",String.class)).isNull();
    assertThat(jdbc.queryForObject("SELECT count(*) FROM market_candles WHERE adjustment_status='RAW_UNADJUSTED'",Long.class)).isEqualTo(2L);
    assertThat(jdbc.queryForObject("SELECT max(close) FROM market_candles",java.math.BigDecimal.class)).isEqualByComparingTo("140");
  }

  private org.springframework.test.web.servlet.ResultActions upload(String type,String name,String content) throws Exception {
    MockMultipartFile file=new MockMultipartFile("file",name,"text/csv",content.stripIndent().getBytes());
    return mvc.perform(multipart("/api/v1/data-import/"+type).file(file));
  }
}
