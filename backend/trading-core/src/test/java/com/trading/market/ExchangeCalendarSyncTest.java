package com.trading.market;
import com.fasterxml.jackson.databind.*;
import java.time.*;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class ExchangeCalendarSyncTest {
 private final ObjectMapper json=new ObjectMapper();
 private final LocalDate day=LocalDate.of(2026,11,25);
 private long time(int h,int m){return day.atTime(h,m).atZone(MarketCalendarService.IST).toInstant().toEpochMilli();}
 private JsonNode rows(String items)throws Exception{return json.readTree("{\"status\":\"success\",\"data\":["+items+"]}");}
 private String open(String exchange,int h,int m){
  return "{\"exchange\":\""+exchange+"\",\"start_time\":"+time(h,m)+",\"end_time\":"+time(15,30)+"}";
 }
 private String holiday(String kind,String closed,String open){
  return "{\"date\":\""+day+"\",\"holiday_type\":\""+kind+"\",\"closed_exchanges\":["+closed+"],\"open_exchanges\":["+open+"]}";
 }
 @Test void exactDateAndStandardHoursAreRequired()throws Exception{
  var result=ExchangeCalendarSync.parse(day,rows(open("NSE",9,15)+","+open("BSE",9,15)),rows(""));
  assertThat(result).hasSize(2).allMatch(s->s.trading()&&s.type().equals("REGULAR")&&s.date().equals(day));
  assertThatThrownBy(()->ExchangeCalendarSync.parse(day.minusDays(1),rows(open("NSE",9,15)),rows("")))
    .isInstanceOf(IllegalArgumentException.class);
 }
 @Test void absentVenueIsNotClosureAndDuplicateIsNotRegular()throws Exception{
  assertThat(ExchangeCalendarSync.parse(day,rows(""),rows(""))).isEmpty();
  assertThat(ExchangeCalendarSync.parse(day,rows(open("NSE",9,15)),rows(""))).hasSize(1);
  assertThat(ExchangeCalendarSync.parse(day,rows(open("NSE",9,15)+","+open("NSE",9,15)),rows(""))).isEmpty();
 }
 @Test void explicitClosureAndContradiction()throws Exception{
  var holiday=rows(holiday("TRADING_HOLIDAY","\"NSE\"",""));
  var result=ExchangeCalendarSync.parse(day,rows(""),holiday);
  assertThat(result).hasSize(1).allMatch(s->!s.trading()&&s.open()==null&&s.close()==null);
  assertThat(ExchangeCalendarSync.parse(day,rows(open("NSE",9,15)),holiday)).isEmpty();
 }
 @Test void specialTimingCannotBecomeRegular()throws Exception{
  var times=rows(open("NSE",9,15));
  assertThat(ExchangeCalendarSync.parse(day,times,rows(holiday("SPECIAL_TIMING","",open("NSE",9,15)))))
    .hasSize(1).allMatch(s->s.type().equals("SPECIAL"));
  assertThat(ExchangeCalendarSync.parse(day,rows(open("NSE",10,0)),rows("")))
    .hasSize(1).allMatch(s->s.type().equals("SPECIAL"));
  assertThat(ExchangeCalendarSync.parse(day,times,rows(holiday("SPECIAL_TIMING","",open("NSE",10,0))))).isEmpty();
 }
 @Test void invalidHolidayEnvelopeFailsBeforeWrite()throws Exception{
  assertThatThrownBy(()->ExchangeCalendarSync.parse(day,rows(open("NSE",9,15)),json.readTree("{\"status\":\"error\"}")))
    .isInstanceOf(IllegalArgumentException.class);
 }
}
