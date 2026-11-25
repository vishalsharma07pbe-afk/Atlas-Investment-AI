package com.trading.market;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortfolioJournalLotsTest {
  private static final LocalDate TODAY=LocalDate.of(2026,11,25);
  private BigDecimal n(String v){return new BigDecimal(v);}
  private Map<String,Object> holding(String quantity,String cost){
    return Map.of("symbol","TEST","asset_type","EQUITY","quantity",n(quantity),"invested",n(cost));
  }
  private Map<String,Object> trade(String type,int days,String quantity,String price){
    return new HashMap<>(Map.of("symbol","TEST","asset_type","EQUITY","transaction_type",type,
      "transaction_date",TODAY.minusDays(days),"quantity",n(quantity),"unit_price",n(price),
      "cash_amount",n(quantity).multiply(n(price))));
  }
  private PortfolioJournalLots.Holding result(Map<String,Object> holding,List<Map<String,Object>> trades){
    return (PortfolioJournalLots.Holding)((List<?>)PortfolioJournalLots.assess(List.of(holding),trades,TODAY).get("holdings")).getFirst();
  }
  @Test void reconstructsPartialFifoWithCalendarAgeAndExactCost(){
    var h=result(holding("5","700"),List.of(trade("BUY",400,"4","100"),trade("BUY",100,"4","150"),trade("SELL",10,"3","200")));
    assertEquals("PROVISIONAL_JOURNAL_RECONCILED",h.status());
    assertEquals(2,h.openLots().size());
    assertEquals(400,h.openLots().getFirst().calendarDaysHeld());
    assertEquals(0,n("1").compareTo(h.openLots().getFirst().quantity()));
    assertEquals(0,n("700").compareTo(h.journalOpenCost()));
  }
  @Test void missingOrMismatchedJournalDoesNotExposeLots(){
    assertEquals("NO_RECORDED_TRADES",result(holding("5","700"),List.of()).status());
    var trades=List.of(trade("BUY",100,"4","150"));
    assertEquals("QUANTITY_MISMATCH",result(holding("5","700"),trades).status());
    var mismatch=result(holding("4","700"),trades);
    assertEquals("COST_BASIS_MISMATCH",mismatch.status());assertTrue(mismatch.openLots().isEmpty());
  }
  @Test void rejectsAmbiguousOrInvalidTradeEvidence(){
    assertEquals("AMBIGUOUS_SAME_DAY_TRADES",result(holding("1","100"),List.of(trade("BUY",10,"2","100"),trade("SELL",10,"1","100"))).status());
    assertEquals("SALE_EXCEEDS_RECORDED_ACQUISITIONS",result(holding("1","100"),List.of(trade("SELL",20,"1","100"),trade("BUY",10,"2","100"))).status());
    var a=trade("BUY",20,"1","100");var b=trade("BUY",10,"1","100");
    a.put("source_reference","duplicate");b.put("source_reference","duplicate");
    assertEquals("DUPLICATE_SOURCE_REFERENCE",result(holding("2","200"),List.of(a,b)).status());
    a.put("cash_amount",n("110"));
    assertEquals("INVALID_OR_UNRECONCILED_TRADE",result(holding("1","100"),List.of(a)).status());
  }
}
