package com.trading.market;
import java.time.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
@Service public class MarketCalendarService {
 public static final ZoneId IST=ZoneId.of("Asia/Kolkata");
 private final JdbcTemplate jdbc;
 public MarketCalendarService(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public boolean isTradingDay(String exchange,LocalDate day){
  if(!Set.of("NSE","BSE").contains(exchange))throw new IllegalArgumentException("exchange");
  if(day.getDayOfWeek()==DayOfWeek.SATURDAY||day.getDayOfWeek()==DayOfWeek.SUNDAY)return false;
  if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM exchange_holidays WHERE exchange_code=? AND holiday_date=?)",Boolean.class,exchange,day)))return false;
  List<Boolean> result=jdbc.query("SELECT ms.is_trading_day FROM market_sessions ms JOIN exchanges e ON e.id=ms.exchange_id WHERE e.code=? AND ms.session_date=? AND ms.session_type='REGULAR'",(rs,n)->rs.getBoolean(1),exchange,day);
  return result.size()==1&&result.get(0);
 }
 /** Exact stored regular-session context for the research coordinator.
  * No inference from a missing calendar row or missing time bounds.
  * Special sessions need a separate validated policy; do not label them open.
  */
 public Map<String,Object> sessionContext(String exchange,Instant instant){
  if(!Set.of("NSE","BSE").contains(exchange))throw new IllegalArgumentException("exchange");
  LocalDate day=instant.atZone(IST).toLocalDate();
  var rows=jdbc.queryForList("""
    SELECT s.session_type,s.is_trading_day,extract(epoch FROM s.open_time) AS open_epoch,
           extract(epoch FROM s.close_time) AS close_epoch,
           EXISTS(SELECT 1 FROM exchange_holidays h WHERE h.exchange_code=e.code AND h.holiday_date=?) AS holiday
    FROM exchanges e LEFT JOIN market_sessions s ON s.exchange_id=e.id AND s.session_date=?
    WHERE e.code=?
    """,day,day,exchange);
  Map<String,Object> result=new LinkedHashMap<>();
  result.put("exchange",exchange);result.put("session_date",day.toString());
  result.put("phase","CALENDAR_UNVERIFIED");result.put("open_at",null);result.put("close_at",null);
  if(rows.isEmpty())return result;
  if(rows.stream().anyMatch(r->Boolean.TRUE.equals(r.get("is_trading_day"))&&!"REGULAR".equals(r.get("session_type")))){
   result.put("phase","SPECIAL_SESSION_UNSUPPORTED");return result;
  }
  if(day.getDayOfWeek()==DayOfWeek.SATURDAY||day.getDayOfWeek()==DayOfWeek.SUNDAY||Boolean.TRUE.equals(rows.getFirst().get("holiday"))){
   result.put("phase","CLOSED");return result;
  }
  var regular=rows.stream().filter(r->"REGULAR".equals(r.get("session_type"))).toList();
  if(regular.size()!=1)return result;
  var row=regular.getFirst();
  if(Boolean.FALSE.equals(row.get("is_trading_day"))){result.put("phase","CLOSED");return result;}
  if(!Boolean.TRUE.equals(row.get("is_trading_day"))||!(row.get("open_epoch") instanceof Number o)||!(row.get("close_epoch") instanceof Number c))return result;
  Instant open=Instant.ofEpochSecond(o.longValue()),close=Instant.ofEpochSecond(c.longValue());
  if(!open.atZone(IST).toLocalDate().equals(day)||!close.atZone(IST).toLocalDate().equals(day)||!open.isBefore(close))return result;
  result.put("open_at",open.toString());result.put("close_at",close.toString());
  result.put("phase",instant.isBefore(open.minusSeconds(5400))?"BEFORE_PRE_MARKET":
     instant.isBefore(open)?"PRE_MARKET":instant.isBefore(close)?"MARKET_HOURS":"POST_MARKET");
  return result;
 }
 public boolean isMarketOpen(){return isMarketOpen("NSE",Instant.now());}
 public boolean isMarketOpen(String exchange){return isMarketOpen(exchange,Instant.now());}
 public boolean isMarketOpen(String exchange,Instant instant){
  ZonedDateTime z=instant.atZone(IST);LocalTime t=z.toLocalTime();
  return !t.isBefore(LocalTime.of(9,15))&&t.isBefore(LocalTime.of(15,30))&&isTradingDay(exchange,z.toLocalDate());
 }
 public LocalDate lastTradingDay(){return lastTradingDay("NSE",LocalDate.now(IST));}
 public LocalDate nextTradingDay(){return nextTradingDay("NSE",LocalDate.now(IST));}
 public LocalDate lastTradingDay(String exchange,LocalDate before){for(int i=1;i<=370;i++){LocalDate d=before.minusDays(i);if(isTradingDay(exchange,d))return d;}throw new IllegalStateException("No published session in prior 370 days");}
 public LocalDate nextTradingDay(String exchange,LocalDate after){for(int i=1;i<=370;i++){LocalDate d=after.plusDays(i);if(isTradingDay(exchange,d))return d;}throw new IllegalStateException("No published session in next 370 days");}
}
