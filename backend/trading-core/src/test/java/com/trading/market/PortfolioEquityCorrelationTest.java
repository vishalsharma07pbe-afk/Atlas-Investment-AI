package com.trading.market;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioEquityCorrelationTest {
 private static final LocalDate TODAY=LocalDate.of(2026,11,24);
 private static List<Map<String,Object>> history(double scale){
  List<Map<String,Object>> rows=new ArrayList<>();
  double price=100;
  for(int i=0;i<=40;i++){
   price*=1+scale*(i%3-1)*0.01;
   rows.add(new HashMap<>(Map.of("trade_date",TODAY.minusDays(41-i),"close",price,
      "source_id",1L,"adjustment_status","ADJUSTED")));
  }
  return rows;
 }
 @Test void comparesOnlyMatchingIntervals(){
  var a=PortfolioEquityCorrelation.returns(history(1),TODAY);
  var b=PortfolioEquityCorrelation.returns(history(2),TODAY);
  var result=PortfolioEquityCorrelation.compare(a,b,TODAY);
  assertNotNull(result);assertEquals(40,result.observations());
  assertEquals(1,result.correlation(),1e-8);
  var opposite=PortfolioEquityCorrelation.compare(a,PortfolioEquityCorrelation.returns(history(-1),TODAY),TODAY);
  assertNotNull(opposite);assertEquals(-1,opposite.correlation(),1e-8);
 }
 @Test void rejectsRawMixedSourcesDuplicateDatesAndStaleSeries(){
  var raw=history(1);raw.getFirst().put("adjustment_status","RAW_UNADJUSTED");
  assertTrue(PortfolioEquityCorrelation.returns(raw,TODAY).isEmpty());
  var mixed=history(1);mixed.getFirst().put("source_id",2L);
  assertTrue(PortfolioEquityCorrelation.returns(mixed,TODAY).isEmpty());
  var duplicate=history(1);duplicate.add(duplicate.getFirst());
  assertTrue(PortfolioEquityCorrelation.returns(duplicate,TODAY).isEmpty());
  assertTrue(PortfolioEquityCorrelation.returns(history(1),TODAY.plusDays(10)).isEmpty());
 }
 @Test void rejectsConstantReturnsAndInsufficientOverlap(){
  var a=PortfolioEquityCorrelation.returns(history(1),TODAY);
  assertNull(PortfolioEquityCorrelation.compare(a,PortfolioEquityCorrelation.returns(history(0),TODAY),TODAY));
  assertNull(PortfolioEquityCorrelation.compare(a,Map.of(),TODAY));
 }
}
