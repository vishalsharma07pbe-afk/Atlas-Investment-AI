package com.trading.market;

import java.io.IOException;
import org.springframework.jdbc.core.JdbcTemplate;

/** Shared operator research credential only. Never stores a token or private owner identity.
 * Database errors propagate instead of treating an unavailable ledger as permission.
 * Existing in-flight requests are not cancelled; this is not a distributed lease.
 */
final class OperatorFeedCooldown {
 private OperatorFeedCooldown(){}
 record Failure(String code,int baseSeconds,long retryAfterSeconds){}

 static boolean blocked(JdbcTemplate jdbc){
  return Boolean.TRUE.equals(jdbc.queryForObject("""
    SELECT EXISTS(SELECT 1 FROM operator_feed_cooldown
      WHERE scope='UPSTOX_OPERATOR' AND blocked_until>now())
    """,Boolean.class));
 }

 static Failure classify(Exception ex){
  if(ex instanceof FeedHttp.ProviderHttpException http){
   int status=http.status();
   String code=switch(status){
    case 401->"UPSTOX_REAUTHORIZATION_REQUIRED";
    case 403->"UPSTOX_ACCESS_OR_ENTITLEMENT_REJECTED";
    case 429->"PROVIDER_RATE_LIMITED";
    case 408->"PROVIDER_TEMPORARY_FAILURE";
    default->status>=500&&status<=599?"PROVIDER_TEMPORARY_FAILURE":null;
   };
   if(code==null)return null;
   return new Failure(code,status==401||status==403?900:60,http.retryAfterSeconds());
  }
  if(ex instanceof IOException)return new Failure("PROVIDER_TRANSPORT_FAILURE",60,0);
  return null;
 }

 static boolean record(JdbcTemplate jdbc,Exception ex){
  Failure failure=classify(ex);
  if(failure==null)return false;
  jdbc.update("""
    INSERT INTO operator_feed_cooldown(scope,failure_code,failure_count,last_failure_at,blocked_until)
    VALUES ('UPSTOX_OPERATOR',?,1,now(),now()+(? * interval '1 second'))
    ON CONFLICT(scope) DO UPDATE SET
      failure_code=EXCLUDED.failure_code,
      failure_count=CASE WHEN operator_feed_cooldown.last_failure_at<now()-interval '24 hours'
        THEN 1 ELSE LEAST(operator_feed_cooldown.failure_count+1,7) END,
      last_failure_at=now(),
      blocked_until=GREATEST(operator_feed_cooldown.blocked_until,EXCLUDED.blocked_until,
        now()+(LEAST(3600,? * (1 << CASE WHEN operator_feed_cooldown.last_failure_at<now()-interval '24 hours'
          THEN 0 ELSE LEAST(operator_feed_cooldown.failure_count,6) END)) * interval '1 second'))
    """,failure.code(),Math.max(failure.baseSeconds(),failure.retryAfterSeconds()),failure.baseSeconds());
  return true;
 }

 static void recovered(JdbcTemplate jdbc){
  // Never clear a block that another request may just have established.
  jdbc.update("DELETE FROM operator_feed_cooldown WHERE scope='UPSTOX_OPERATOR' AND blocked_until<=now()");
 }
}
