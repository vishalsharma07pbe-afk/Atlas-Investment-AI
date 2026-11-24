package com.trading.market;
import java.time.*;
import java.math.BigDecimal;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class FundHistoryResearchServiceTest {
 @Test void automaticRequestsRequirePermission(){
  JdbcTemplate jdbc=mock(JdbcTemplate.class);AmfiFeedService funds=mock(AmfiFeedService.class);
  var service=new FundHistoryResearchService(jdbc,funds);service.enabled=true;service.scheduled();
  verifyNoInteractions(jdbc,funds);
 }
 @Test void datedHistoryWithAmfiAnchorProducesObservedReturns(){
  LocalDate end=LocalDate.of(2026,11,24);
  List<Map<String,Object>> rows=new ArrayList<>();
  for(int i=0;i<=1100;i++)rows.add(Map.of("nav_date",end.minusDays(1100-i),"nav",BigDecimal.valueOf(100+i*.01),"source_code",i==1100?"AMFI":"MFAPI"));
  var result=FundHistoryResearchService.metrics(rows,end);
  assertNotNull(result);assertEquals(0.0,result.get("drawdown_3y_percent"));
  assertTrue((Double)result.get("cagr_3y_percent")>0);
  assertNull(FundHistoryResearchService.metrics(rows,end.plusDays(8)));
  assertNull(FundHistoryResearchService.metrics(rows.subList(0,100),end));
 }
}
