package com.trading.market;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
class MarketSchedulerTest {
 @Test void retryBackoff(){assertThat(MarketIngestionScheduler.backoffSeconds(1,30,3600)).isEqualTo(30);assertThat(MarketIngestionScheduler.backoffSeconds(2,30,3600)).isEqualTo(60);assertThat(MarketIngestionScheduler.backoffSeconds(20,30,3600)).isEqualTo(3600);}
 @Test void marketBoundaries(){
  JdbcTemplate jdbc=mock(JdbcTemplate.class);
  when(jdbc.query(anyString(),any(org.springframework.jdbc.core.RowMapper.class),eq("NSE"),eq(LocalDate.of(2026,11,16)))).thenReturn(List.of(true));
  when(jdbc.queryForObject(anyString(),eq(Boolean.class),eq("NSE"),eq(LocalDate.of(2026,11,16)))).thenReturn(false);
  MarketCalendarService c=new MarketCalendarService(jdbc);
  assertThat(c.isMarketOpen("NSE",ZonedDateTime.of(2026,11,16,9,14,0,0,MarketCalendarService.IST).toInstant())).isFalse();
  assertThat(c.isMarketOpen("NSE",ZonedDateTime.of(2026,11,16,9,15,0,0,MarketCalendarService.IST).toInstant())).isTrue();
  assertThat(c.isMarketOpen("NSE",ZonedDateTime.of(2026,11,16,15,30,0,0,MarketCalendarService.IST).toInstant())).isFalse();
  assertThat(c.isTradingDay("NSE",LocalDate.of(2026,11,14))).isFalse();
  when(jdbc.queryForObject(anyString(),eq(Boolean.class),eq("NSE"),eq(LocalDate.of(2026,11,10)))).thenReturn(true);
  assertThat(c.isTradingDay("NSE",LocalDate.of(2026,11,10))).isFalse();
 }
}
