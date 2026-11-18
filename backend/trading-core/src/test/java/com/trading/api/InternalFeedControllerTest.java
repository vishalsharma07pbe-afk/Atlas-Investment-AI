package com.trading.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

class InternalFeedControllerTest {
  private InternalFeedController controller(JdbcTemplate jdbc,String token) {
    return new InternalFeedController(jdbc,mock(InstrumentController.class),
      mock(MarketDataController.class),mock(DataHealthController.class),token);
  }

  @Test void returnsOnlyResolvedPublicInstrumentSelections() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    when(jdbc.queryForList(contains("DISTINCT upper(symbol)"),eq(String.class)))
      .thenReturn(List.of("MISSING","RELIANCE"));
    when(jdbc.queryForList(contains("row_number()"))).thenReturn(List.of(
      new LinkedHashMap<>(Map.of("symbol","RELIANCE","instrument_key","NSE_EQ|INE002A01018",
        "exchange_code","NSE","instrument_type","EQ"))));
    Map<String,Object> result=controller(jdbc,"service-secret").equitySubscriptions(request);
    assertThat(result.get("resolved_count")).isEqualTo(1);
    assertThat(result.get("missing_symbols")).isEqualTo(List.of("MISSING"));
    assertThat(result).doesNotContainKeys("user_id","quantity");
  }

  @Test void rejectsMissingOrIncorrectServiceToken() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    when(request.getHeader(anyString())).thenReturn("wrong");
    InternalFeedController controller=controller(jdbc,"service-secret");
    assertThatThrownBy(()->controller.equitySubscriptions(request))
      .isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
  }

  @Test void protectsAndDelegatesReadOnlyResearchData() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    InstrumentController instruments=mock(InstrumentController.class);
    MarketDataController marketData=mock(MarketDataController.class);
    DataHealthController dataHealth=mock(DataHealthController.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    when(instruments.list(20,null,"NSE")).thenReturn(List.of(Map.of("symbol","TCS")));
    when(marketData.candles(7,250)).thenReturn(Map.of("count",21));
    InternalFeedController controller=new InternalFeedController(jdbc,instruments,marketData,dataHealth,"service-secret");
    assertThat(controller.instruments(request,20,null,"NSE")).hasSize(1);
    assertThat(controller.candles(request,7,250)).containsEntry("count",21);
    verify(instruments).list(20,null,"NSE");
    verify(marketData).candles(7,250);
  }
}
