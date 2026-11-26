package com.trading.market;
import java.io.IOException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class OperatorFeedCooldownTest {
 @Test void classifiesOnlySharedTransportFailures(){
  assertEquals(900,OperatorFeedCooldown.classify(new FeedHttp.ProviderHttpException(401)).baseSeconds());
  assertEquals(900,OperatorFeedCooldown.classify(new FeedHttp.ProviderHttpException(403)).baseSeconds());
  assertEquals(600,OperatorFeedCooldown.classify(new FeedHttp.ProviderHttpException(429,600)).retryAfterSeconds());
  assertEquals(60,OperatorFeedCooldown.classify(new FeedHttp.ProviderHttpException(503)).baseSeconds());
  assertEquals("PROVIDER_TRANSPORT_FAILURE",OperatorFeedCooldown.classify(new IOException("secret test body")).code());
  assertNull(OperatorFeedCooldown.classify(new FeedHttp.ProviderHttpException(404)));
  assertNull(OperatorFeedCooldown.classify(new IllegalArgumentException("invalid evidence")));
 }
 @Test void identifiesUpstoxWithoutChangingAuthorization(){
  var api=FeedHttp.request("https://api.upstox.com/v2/market/holidays",null);
  assertEquals("ATLAS/2.0",api.headers().firstValue("User-Agent").orElseThrow());
  assertEquals("application/json",api.headers().firstValue("Accept").orElseThrow());
  assertTrue(api.headers().firstValue("Authorization").isEmpty());
  assertEquals("GET",api.method());
  var historical=FeedHttp.request("https://api.upstox.com/v3/historical-candle/test","synthetic-token");
  assertEquals("Bearer synthetic-token",historical.headers().firstValue("Authorization").orElseThrow());
  assertEquals("ATLAS/2.0",historical.headers().firstValue("User-Agent").orElseThrow());
  var registry=FeedHttp.request("https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz",null);
  assertEquals("ATLAS/2.0",registry.headers().firstValue("User-Agent").orElseThrow());
  assertTrue(registry.headers().firstValue("Authorization").isEmpty());
  assertTrue(FeedHttp.request("https://example.test/api",null).headers().firstValue("User-Agent").isEmpty());
  assertThrows(IllegalArgumentException.class,()->FeedHttp.request("http://api.upstox.com/test",null));
 }
 @Test void numericRetryAfterIsBounded(){
  assertEquals(600,FeedHttp.numericRetryAfter("600"));
  assertEquals(3600,FeedHttp.numericRetryAfter("999999999999"));
  assertEquals(0,FeedHttp.numericRetryAfter("Wed, 25 Nov 2026 12:00:00 GMT"));
  assertEquals(0,FeedHttp.numericRetryAfter("-5"));
  assertEquals(0,FeedHttp.numericRetryAfter(null));
 }
}
