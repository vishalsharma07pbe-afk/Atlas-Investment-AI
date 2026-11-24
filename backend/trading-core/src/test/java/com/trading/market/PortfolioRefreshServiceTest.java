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

  @Test void boundedBackgroundBatchUsesOwnerFromClaimedRow(){
    JdbcTemplate jdbc=mock(JdbcTemplate.class);
    UpstoxFeedService provider=mock(UpstoxFeedService.class);
    when(jdbc.queryForList(contains("FOR UPDATE SKIP LOCKED"),eq(10))).thenReturn(List.of());
    var result=new PortfolioRefreshService(jdbc,provider).refreshDue(100);
    assertEquals(0,result.get("total"));
    verify(jdbc).queryForList(contains("RETURNING h.id,h.user_id"),eq(10));
    verifyNoInteractions(provider);
  }
}
