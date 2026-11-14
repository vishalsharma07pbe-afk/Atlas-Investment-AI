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
  List<Boolean> result=jdbc.query("SELECT ms.is_trading_day FROM market_sessions ms JOIN exchanges e ON e.id=ms.exchange_id WHERE e.code=? AND ms.session_date=? AND ms.session_type='REGULAR'",(rs,n)->rs.getBoolean(1),exchange,day);
  return result.size()==1&&result.get(0);
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
