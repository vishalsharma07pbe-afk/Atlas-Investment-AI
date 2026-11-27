package com.trading.market;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class DiscoveryQuoteSchedulerTest {
 private final ObjectMapper json=new ObjectMapper();
 private final Instant open=Instant.parse("2026-11-27T03:45:00Z"), close=Instant.parse("2026-11-27T10:00:00Z");
 private final Instant now=Instant.parse("2026-11-27T06:00:00Z");
 private final DiscoveryQuoteScheduler.Identity id=new DiscoveryQuoteScheduler.Identity(1,"NSE_EQ|INE002A01018","INE002A01018","TEST");
 private com.fasterxml.jackson.databind.node.ObjectNode quote(){
  var q=json.createObjectNode().put("instrument_token",id.key()).put("symbol",id.symbol()).put("last_trade_time",Long.toString(now.minusSeconds(10).toEpochMilli()))
    .put("timestamp",now.toString()).put("last_price",102).put("prev_close_price",100).put("average_price",101).put("volume",200000);
  var depth=q.putObject("depth");depth.putArray("buy").addObject().put("price",101.9);depth.putArray("sell").addObject().put("price",102.1);
  return q;
 }
 @Test void permissionsRequired(){
  var db=mock(JdbcTemplate.class);var http=mock(FeedHttp.class);var calendar=mock(MarketCalendarService.class);
  var s=new DiscoveryQuoteScheduler(db,http,calendar);s.enabled=true;s.rights=true;s.token="fixture";s.scheduled();
  verifyNoInteractions(db,http,calendar);
 }
 @Test void liquidCurrentQuoteIsPriorityButPumpAndThinBookAreNot(){
  var q=quote();var o=DiscoveryQuoteScheduler.parse(q,id,open,close,now);
  assertNotNull(o);assertTrue(o.priority());assertEquals(2.0,o.change(),.0001);
  q.put("last_price",120);assertFalse(DiscoveryQuoteScheduler.parse(q,id,open,close,now).priority());
  q.put("last_price",102);q.put("volume",100);assertFalse(DiscoveryQuoteScheduler.parse(q,id,open,close,now).priority());
  q.put("volume",200000);q.remove("depth");assertFalse(DiscoveryQuoteScheduler.parse(q,id,open,close,now).priority());
 }
 @Test void staleFutureAndMismatchedObservationsAreWithheld(){
  var q=quote();q.put("last_trade_time",Long.toString(now.minusSeconds(901).toEpochMilli()));assertNull(DiscoveryQuoteScheduler.parse(q,id,open,close,now));
  q=quote();q.put("timestamp",now.plusSeconds(10).toString());assertNull(DiscoveryQuoteScheduler.parse(q,id,open,close,now));
  q=quote();q.put("symbol","OTHER");assertNull(DiscoveryQuoteScheduler.parse(q,id,open,close,now));
  q=quote();q.put("volume",0);assertNull(DiscoveryQuoteScheduler.parse(q,id,open,close,now));
 }
 @Test void partialResponsesAllowedButUnexpectedAndDuplicateKeysRejected(){
  var root=json.createObjectNode().put("status","success");var data=root.putObject("data");
  var requested=Map.of(id.key(),id);
  assertTrue(DiscoveryQuoteScheduler.validateEnvelope(root,requested).isEmpty());
  data.set("NSE_EQ:TEST",quote());assertEquals(1,DiscoveryQuoteScheduler.validateEnvelope(root,requested).size());
  data.set("NSE_EQ:OTHER",quote().put("instrument_token","NSE_EQ|OTHER"));
  assertThrows(IllegalStateException.class,()->DiscoveryQuoteScheduler.validateEnvelope(root,requested));
 }
}
