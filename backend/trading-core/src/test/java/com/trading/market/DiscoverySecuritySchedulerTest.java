package com.trading.market;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.support.TransactionTemplate;
class DiscoverySecuritySchedulerTest {
 private final ObjectMapper json=new ObjectMapper();
 @Test void providerSecurityTypesAreExplicitAndUnknownByDefault(){
  assertEquals("PCA",UpstoxFeedService.securityType(json.createObjectNode().put("security_type","PCA")));
  assertEquals("SME",UpstoxFeedService.securityType(json.createObjectNode().put("security_type","SME")));
  assertEquals("UNKNOWN",UpstoxFeedService.securityType(json.createObjectNode()));
  assertEquals("UNKNOWN",UpstoxFeedService.securityType(json.createObjectNode().put("security_type","UNRECOGNIZED")));
 }
 @Test void exactSuspendedIdentityIsRequired()throws Exception{
  var rows=json.createArrayNode();
  rows.addObject().put("exchange","NSE").put("segment","NSE_EQ").put("isin","INE002A01018").put("instrument_key","NSE_EQ|INE002A01018");
  assertEquals(1,DiscoverySecurityScheduler.parse(rows).size());
  rows.add(rows.get(0).deepCopy());
  assertThrows(IllegalArgumentException.class,()->DiscoverySecurityScheduler.parse(rows));
  rows.remove(1);
  ((com.fasterxml.jackson.databind.node.ObjectNode)rows.get(0)).put("instrument_key","NSE_EQ|INE009A01021");
  assertThrows(IllegalArgumentException.class,()->DiscoverySecurityScheduler.parse(rows));
 }
 @Test void noProviderCallWhenRightsDisabled(){
  var db=mock(JdbcTemplate.class);var http=mock(FeedHttp.class);var tx=mock(TransactionTemplate.class);
  var scheduler=new DiscoverySecurityScheduler(db,http,tx);scheduler.enabled=true;scheduler.scheduled();
  verifyNoInteractions(db,http,tx);
 }
}
