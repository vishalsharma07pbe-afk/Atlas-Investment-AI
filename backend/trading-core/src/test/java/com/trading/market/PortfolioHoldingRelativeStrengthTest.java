package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioHoldingRelativeStrengthTest {
 @Test void exactCalendarAndPriceSourceAreRequired(){
  LocalDate today=LocalDate.of(2026,11,27);
  var calendar=new TreeMap<LocalDate,String>();
  var stock=new ArrayList<PortfolioHoldingRelativeStrength.Point>();
  var benchmark=new ArrayList<PortfolioHoldingRelativeStrength.Point>();
  for(int i=0;i<100;i++){
   LocalDate d=today.minusDays(100-i);
   boolean regular=d.getDayOfWeek().getValue()<=5;
   calendar.put(d,regular?"REGULAR":"CLOSED");
   if(regular){
    stock.add(new PortfolioHoldingRelativeStrength.Point(d,BigDecimal.valueOf(100+i), "UPSTOX",true));
    benchmark.add(new PortfolioHoldingRelativeStrength.Point(d,BigDecimal.valueOf(100+i/2d),"UPSTOX",true));
   }
  }
  var good=PortfolioHoldingRelativeStrength.compare(stock,benchmark,calendar,today);
  assertEquals("MATCHED_PRICE_INDEX_OBSERVATIONS",good.get("status"));
  assertTrue(((Map<?,?>)good.get("windows")).containsKey("60"));
  stock.removeLast();
  assertEquals("UNAVAILABLE",PortfolioHoldingRelativeStrength.compare(stock,benchmark,calendar,today).get("status"));
 }
 @Test void missingCalendarAndInvalidLatestBenchmarkFailClosed(){
  LocalDate today=LocalDate.of(2026,11,27);
  var calendar=new TreeMap<LocalDate,String>();
  var points=new ArrayList<PortfolioHoldingRelativeStrength.Point>();
  for(int i=1;i<=25;i++){
   LocalDate d=today.minusDays(i);calendar.put(d,"REGULAR");
   points.add(new PortfolioHoldingRelativeStrength.Point(d,BigDecimal.TEN,"UPSTOX",true));
  }
  assertEquals("MATCHED_PRICE_INDEX_OBSERVATIONS",PortfolioHoldingRelativeStrength.compare(points,points,calendar,today).get("status"));
  calendar.put(today.minusDays(3),"UNKNOWN");
  assertEquals("UNAVAILABLE",PortfolioHoldingRelativeStrength.compare(points,points,calendar,today).get("status"));
  calendar.put(today.minusDays(3),"REGULAR");
  var bad=new ArrayList<>(points);bad.set(0,new PortfolioHoldingRelativeStrength.Point(today.minusDays(1),BigDecimal.TEN,"OTHER",true));
  assertEquals("UNAVAILABLE",PortfolioHoldingRelativeStrength.compare(points,bad,calendar,today).get("status"));
 }
}
