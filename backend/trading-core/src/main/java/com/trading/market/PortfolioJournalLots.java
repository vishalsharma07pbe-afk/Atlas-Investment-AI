package com.trading.market;

import java.math.*;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;

/** Provisional FIFO of recorded journal rows, not broker tax lots. */
final class PortfolioJournalLots {
  private PortfolioJournalLots(){}
  private static final int LIMIT=5000;
  record Lot(LocalDate acquired,BigDecimal quantity,BigDecimal unitPrice){}
  record OpenLot(String acquired,BigDecimal quantity,BigDecimal unitPrice,long calendarDaysHeld){}
  record Holding(String symbol,String assetType,String status,BigDecimal recordedQuantity,
      BigDecimal journalQuantity,BigDecimal journalOpenCost,BigDecimal recordedCost,List<OpenLot> openLots){}
  static Map<String,Object> collect(JdbcTemplate jdbc,UUID owner,List<Map<String,Object>> holdings,LocalDate today){
    var trades=jdbc.queryForList("""
      SELECT symbol,asset_type,transaction_type,transaction_date,quantity,unit_price,cash_amount,source_reference
      FROM portfolio_transactions WHERE user_id=? AND transaction_type IN ('BUY','SELL')
      ORDER BY transaction_date,id LIMIT 5001
      """,owner);
    return assess(holdings,trades,today);
  }
  private static String key(Map<String,Object> row){
    return row.get("asset_type")+":"+String.valueOf(row.get("symbol")).toUpperCase(Locale.ROOT);
  }
  private static LocalDate day(Object o){return o instanceof java.sql.Date d?d.toLocalDate():o instanceof LocalDate d?d:null;}
  private static BigDecimal amount(Map<String,Object> row,String field){
    return row.get(field) instanceof BigDecimal v&&Double.isFinite(v.doubleValue())?v:null;
  }
  static Map<String,Object> assess(List<Map<String,Object>> holdings,List<Map<String,Object>> trades,LocalDate today){
    var out=new LinkedHashMap<String,Object>();
    out.put("notice","Provisional FIFO reconstruction from recorded journal entries matched by asset type and symbol, not verified broker, demat or fund folio tax lots. Same-day mixed buys and sales, duplicate source references, inconsistent amounts, missing history and quantity or cost mismatches are withheld. Calendar days are descriptive, not a tax classification. Corporate actions, transfers, fees, grandfathering and tax rules are not established. No capital gains tax estimate.");
    out.put("holdings",List.of());out.put("reconciled_count",0);
    if(trades.size()>LIMIT){out.put("status","JOURNAL_LIMIT_EXCEEDED");return out;}
    Map<String,List<Map<String,Object>>> byKey=new HashMap<>();
    for(var row:trades)byKey.computeIfAbsent(key(row),k->new ArrayList<>()).add(row);
    Map<String,Long> counts=new HashMap<>();
    for(var row:holdings)counts.merge(key(row),1L,Long::sum);
    List<Holding> results=new ArrayList<>();
    for(var h:holdings){
      String symbol=String.valueOf(h.get("symbol")),asset=String.valueOf(h.get("asset_type"));
      BigDecimal quantity=amount(h,"quantity"),cost=amount(h,"invested");
      String k=key(h);
      List<Map<String,Object>> history=byKey.getOrDefault(k,List.of());
      String status=null;
      if(quantity==null||quantity.signum()<=0||cost==null||cost.signum()<0||counts.get(k)!=1L||
          !Set.of("EQUITY","MUTUAL_FUND").contains(asset))status="AMBIGUOUS_RECORDED_HOLDING";
      else if(history.isEmpty())status="NO_RECORDED_TRADES";
      Deque<Lot> lots=new ArrayDeque<>();
      Map<LocalDate,Set<String>> types=new HashMap<>();
      Set<String> refs=new HashSet<>();
      if(status==null)for(var t:history){
        LocalDate d=day(t.get("transaction_date"));
        String type=String.valueOf(t.get("transaction_type"));
        BigDecimal q=amount(t,"quantity"),p=amount(t,"unit_price"),cash=amount(t,"cash_amount");
        if(d==null||d.isAfter(today)||d.isBefore(LocalDate.of(1970,1,1))||
          !Set.of("BUY","SELL").contains(type)||q==null||q.signum()<=0||p==null||p.signum()<=0||
          cash==null||cash.signum()<=0||q.multiply(p).subtract(cash).abs().compareTo(new BigDecimal("0.01"))>0){
          status="INVALID_OR_UNRECONCILED_TRADE";break;
        }
        // Multiple same-day purchases are also ambiguous if prices differ and
        // any later sale may consume only part of that day's acquisitions.
        if(!types.computeIfAbsent(d,x->new HashSet<>()).add(type)&&"BUY".equals(type)){
          status="AMBIGUOUS_SAME_DAY_ACQUISITIONS";break;
        }
        if(types.get(d).size()>1){status="AMBIGUOUS_SAME_DAY_TRADES";break;}
        if(t.get("source_reference") instanceof String ref&&!ref.isBlank()&&!refs.add(ref)){
          status="DUPLICATE_SOURCE_REFERENCE";break;
        }
      }
      if(status==null){
        var ordered=history.stream().sorted(Comparator.comparing(t->day(t.get("transaction_date")))).toList();
        for(var t:ordered){
          BigDecimal q=amount(t,"quantity"),p=amount(t,"unit_price");
          if("BUY".equals(t.get("transaction_type")))lots.addLast(new Lot(day(t.get("transaction_date")),q,p));
          else{
            while(q.signum()>0&&!lots.isEmpty()){
              Lot first=lots.removeFirst();BigDecimal consumed=q.min(first.quantity());
              q=q.subtract(consumed);BigDecimal left=first.quantity().subtract(consumed);
              if(left.signum()>0)lots.addFirst(new Lot(first.acquired(),left,first.unitPrice()));
            }
            if(q.signum()>0){status="SALE_EXCEEDS_RECORDED_ACQUISITIONS";break;}
          }
        }
      }
      BigDecimal journalQuantity=null,journalCost=null;List<OpenLot> visible=List.of();
      if(status==null){
        journalQuantity=lots.stream().map(Lot::quantity).reduce(BigDecimal.ZERO,BigDecimal::add);
        journalCost=lots.stream().map(l->l.quantity().multiply(l.unitPrice())).reduce(BigDecimal.ZERO,BigDecimal::add);
        if(journalQuantity.compareTo(quantity)!=0)status="QUANTITY_MISMATCH";
        else if(journalCost.subtract(cost).abs().compareTo(new BigDecimal("0.01"))>0)status="COST_BASIS_MISMATCH";
        else if(lots.size()>100)status="OPEN_LOT_LIMIT_EXCEEDED";
        else{
          status="PROVISIONAL_JOURNAL_RECONCILED";
          visible=lots.stream().map(l->new OpenLot(l.acquired().toString(),l.quantity(),l.unitPrice(),ChronoUnit.DAYS.between(l.acquired(),today))).toList();
        }
      }
      results.add(new Holding(symbol,asset,status,quantity,journalQuantity,journalCost,cost,visible));
    }
    long count=results.stream().filter(h->"PROVISIONAL_JOURNAL_RECONCILED".equals(h.status())).count();
    out.put("status",results.isEmpty()?"NO_HOLDINGS":count==0?"NO_RECONCILED_HOLDINGS":count==results.size()?"PROVISIONAL_JOURNAL_RECONCILED":"PARTIAL_JOURNAL_RECONCILIATION");
    out.put("reconciled_count",count);out.put("holdings",results);return out;
  }
}
