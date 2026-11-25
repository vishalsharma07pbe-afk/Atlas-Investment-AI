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
 @Test void numericRetryAfterIsBounded(){
  assertEquals(600,FeedHttp.numericRetryAfter("600"));
  assertEquals(3600,FeedHttp.numericRetryAfter("999999999999"));
  assertEquals(0,FeedHttp.numericRetryAfter("Wed, 25 Nov 2026 12:00:00 GMT"));
  assertEquals(0,FeedHttp.numericRetryAfter("-5"));
  assertEquals(0,FeedHttp.numericRetryAfter(null));
 }
}
