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

  @Test void discoveryBatchRequiresTokenAndBoundedUniqueIds() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    InternalFeedController controller=controller(jdbc,"service-secret");
    assertThatThrownBy(()->controller.discoveryUniverse(request,"NSE")).isInstanceOf(ResponseStatusException.class);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    assertThatThrownBy(()->controller.discoveryCandles(request,"NSE",List.of(7L,7L))).isInstanceOf(ResponseStatusException.class);
    assertThatThrownBy(()->controller.discoveryCandles(request,"OTHER",List.of(7L))).isInstanceOf(ResponseStatusException.class);
    assertThatThrownBy(()->controller.discoveryCandles(request,"NSE",java.util.stream.LongStream.rangeClosed(1,21).boxed().toList())).isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
  }

  @Test void strategyBenchmarkRequiresCredentialAndUsesFixedPublicIndex() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    var api=controller(jdbc,"service-secret");
    assertThatThrownBy(()->api.strategyBenchmark(request)).isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    when(jdbc.queryForList(contains("NSE_INDEX|Nifty 50"))).thenReturn(List.of(Map.of("close",100)));
    assertThat(api.strategyBenchmark(request)).containsEntry("benchmark_key","NSE_INDEX|Nifty 50")
      .containsEntry("kind","PRICE_INDEX").doesNotContainKeys("user_id","quantity");
    verify(jdbc).queryForList(contains("NSE_INDEX|Nifty 50"));
  }

  @Test void strategyCalendarRequiresCredentialAndKnownVenue() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    var api=controller(jdbc,"service-secret");
    assertThatThrownBy(()->api.strategyCalendar(request,"NSE")).isInstanceOf(ResponseStatusException.class);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    assertThatThrownBy(()->api.strategyCalendar(request,"OTHER")).isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
    when(jdbc.queryForList(contains("generate_series(1,1100)"),any(java.time.LocalDate.class),eq("NSE")))
      .thenReturn(List.of(Map.of("trade_date","2026-11-11","state","REGULAR")));
    assertThat(api.strategyCalendar(request,"NSE")).containsEntry("exchange","NSE").containsKey("days");
    verify(jdbc).queryForList(contains("generate_series(1,1100)"),any(java.time.LocalDate.class),eq("NSE"));
  }

  @Test void sessionContextRequiresInternalCredential() {
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    var api=controller(jdbc,"service-secret");
    assertThatThrownBy(()->api.sessionContext(request)).isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    var result=api.sessionContext(request);
    assertThat(result).containsEntry("timezone","Asia/Kolkata");
    assertThat((List<?>)result.get("sessions")).hasSize(2);
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

  @Test void capPublicationRequiresServiceCredentialAndRightsAndCompleteDatedRows(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    HttpServletRequest request=mock(HttpServletRequest.class);
    var api=controller(jdbc,"service-secret");
    var body=new com.fasterxml.jackson.databind.ObjectMapper().createObjectNode();
    assertThatThrownBy(()->api.amfiEquityCaps(request,body)).isInstanceOf(ResponseStatusException.class);
    when(request.getHeader("X-Atlas-Service-Token")).thenReturn("service-secret");
    assertThatThrownBy(()->api.amfiEquityCaps(request,body)).isInstanceOf(ResponseStatusException.class);
    api.capUsageRights=true;
    assertThatThrownBy(()->api.amfiEquityCaps(request,body)).isInstanceOf(ResponseStatusException.class);
    verifyNoInteractions(jdbc);
  }
}
