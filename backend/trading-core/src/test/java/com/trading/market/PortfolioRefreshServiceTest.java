package com.trading.market;

import java.util.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class PortfolioRefreshServiceTest {
  @Test void refreshesNavForExplicitOwnerWithoutBrokerAccess(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    UUID owner=UUID.randomUUID();
    java.sql.Date date=java.sql.Date.valueOf(LocalDate.now().minusDays(1));
    BigDecimal nav=new BigDecimal("101.25");
    when(jdbc.queryForList(contains("SELECT id,user_id,symbol,asset_type"),eq(owner)))
      .thenReturn(List.of(Map.of("id",7L,"user_id",owner,"symbol","123","asset_type","MUTUAL_FUND")));
    when(jdbc.queryForList(contains("FROM mutual_fund_nav"),eq(123L)))
      .thenReturn(List.of(Map.of("nav",nav,"nav_date",date)));
    when(jdbc.update(contains("WHERE id=? AND user_id=? AND symbol=?"),eq(nav),isNull(),eq(date),eq(7L),eq(owner),eq("123"),eq(date))).thenReturn(1);
    var result=new PortfolioRefreshService(jdbc,provider).refreshUser(owner,false);
    assertEquals(1,result.get("updated"));
    verifyNoInteractions(provider);
  }

  @Test void rejectedAuthorizationDoesNotRetryEachHoldingInSamePass()throws Exception{
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    UUID owner=UUID.randomUUID();
    when(jdbc.queryForList(contains("SELECT id,user_id,symbol,asset_type"),eq(owner)))
      .thenReturn(List.of(Map.of("id",7L,"user_id",owner,"symbol","ONE","asset_type","EQUITY"),
        Map.of("id",8L,"user_id",owner,"symbol","TWO","asset_type","EQUITY")));
    when(jdbc.queryForList(contains("SELECT m.instrument_key"),eq(String.class),eq("ONE")))
      .thenReturn(List.of("NSE_EQ|INE002A01018"));
    when(provider.quote(owner,"NSE_EQ|INE002A01018")).thenThrow(new FeedHttp.ProviderHttpException(401));
    var result=new PortfolioRefreshService(jdbc,provider).refreshUser(owner,false);
    assertEquals(0,result.get("updated"));
    assertTrue(result.get("skipped").toString().contains("UPSTOX_REAUTHORIZATION_REQUIRED"));
    verify(provider,times(1)).quote(eq(owner),anyString());
    verify(jdbc,never()).queryForList(contains("SELECT m.instrument_key"),eq(String.class),eq("TWO"));
  }

  @Test void invalidAndFutureNavObservationsCannotOverwriteHoldings(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    UUID owner=UUID.randomUUID();
    when(jdbc.queryForList(contains("SELECT id,user_id,symbol,asset_type"),eq(owner)))
      .thenReturn(List.of(Map.of("id",7L,"user_id",owner,"symbol","123","asset_type","MUTUAL_FUND")));
    when(jdbc.queryForList(contains("FROM mutual_fund_nav"),eq(123L)))
      .thenReturn(List.of(Map.of("nav",BigDecimal.ONE,"nav_date",LocalDate.now(MarketCalendarService.IST).plusDays(1))),
                  List.of(Map.of("nav",BigDecimal.ZERO,"nav_date",LocalDate.now(MarketCalendarService.IST))));
    var service=new PortfolioRefreshService(jdbc,provider);
    assertTrue(service.refreshUser(owner,false).get("skipped").toString().contains("INVALID_NAV_OBSERVATION"));
    assertTrue(service.refreshUser(owner,false).get("skipped").toString().contains("INVALID_NAV_OBSERVATION"));
    verify(jdbc,never()).update(anyString(),any(),any(),any(),any(),any(),any(),any());
    verifyNoInteractions(provider);
  }

  @Test void boundedBackgroundBatchUsesOwnerFromClaimedRow(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    when(jdbc.queryForList(contains("FOR UPDATE SKIP LOCKED"),eq(false),eq(10))).thenReturn(List.of());
    var result=new PortfolioRefreshService(jdbc,provider).refreshDue(100);
    assertEquals(0,result.get("total"));
    verify(jdbc).queryForList(contains("RETURNING h.id,h.user_id"),eq(false),eq(10));
    verify(provider).hasConfiguredMarketToken();
    verifyNoMoreInteractions(provider);
  }
  @Test void explicitFundRefreshNeverRequestsStockProviders(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    UUID owner=UUID.randomUUID();
    when(jdbc.queryForList(contains("AND asset_type='MUTUAL_FUND'"),eq(owner))).thenReturn(List.of());
    var result=new PortfolioRefreshService(jdbc,provider).refreshFunds(owner);
    assertEquals(0,result.get("total"));
    verifyNoInteractions(provider);
  }

}
