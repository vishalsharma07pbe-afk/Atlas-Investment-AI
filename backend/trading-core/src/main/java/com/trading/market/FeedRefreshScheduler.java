package com.trading.market;

import java.time.*;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Durable per-provider claims for the two public catalog jobs, not owner credentials. */
@Service public class FeedRefreshScheduler {
 private final JdbcTemplate jdbc;
 private final UpstoxFeedService stocks;
 private final AmfiFeedService funds;
 private final MarketCalendarService calendar;
 private final TransactionTemplate transactions;
 @Value("${atlas.market.feeds.enabled:false}") boolean enabled;
 public FeedRefreshScheduler(JdbcTemplate jdbc,UpstoxFeedService stocks,AmfiFeedService funds,
     MarketCalendarService calendar,TransactionTemplate transactions){
  this.jdbc=jdbc;this.stocks=stocks;this.funds=funds;this.calendar=calendar;this.transactions=transactions;
 }
 @Scheduled(cron="0 10 8 * * MON-FRI",zone="Asia/Kolkata")
 public void master(){
  if(enabled&&calendar.isTradingDay("NSE",LocalDate.now(MarketCalendarService.IST)))attempt("UPSTOX","MASTER",false);
 }
 @Scheduled(initialDelayString="${atlas.market.feeds.master-initial-delay-ms:5000}",fixedDelayString="${atlas.market.feeds.master-check-ms:3600000}")
 public void ensureMaster(){
  if(!enabled)return;
  Boolean needed=jdbc.queryForObject("""
    SELECT EXISTS(SELECT 1 FROM (VALUES ('NSE'),('BSE')) AS venues(code)
      WHERE NOT EXISTS(SELECT 1 FROM upstox_instrument_map m WHERE m.exchange_code=venues.code)
        OR EXISTS(SELECT 1 FROM upstox_instrument_map m WHERE m.exchange_code=venues.code AND m.display_name IS NULL)
        OR (SELECT max(m.updated_at) FROM upstox_instrument_map m WHERE m.exchange_code=venues.code)<now()-interval '36 hours')
    """,Boolean.class);
  if(Boolean.TRUE.equals(needed))attempt("UPSTOX","MASTER_AUTO",false);
 }
 @Scheduled(cron="0 0 22 * * MON-FRI",zone="Asia/Kolkata")
 public void amfi(){if(enabled)attempt("AMFI","NAV",false);}
 @Scheduled(initialDelayString="${atlas.market.feeds.nav-initial-delay-ms:10000}",fixedDelayString="${atlas.market.feeds.nav-check-ms:3600000}")
 public void ensureNav(){
  if(!enabled)return;
  LocalDate latest=jdbc.query("""
    SELECT max(nav_date) latest FROM mutual_fund_nav WHERE source_code='AMFI'
      AND nav_date<=(now() AT TIME ZONE 'Asia/Kolkata')::date
    """,rs->{if(!rs.next())return null;java.sql.Date value=rs.getDate("latest");return value==null?null:value.toLocalDate();});
  if(latest==null||latest.isBefore(LocalDate.now(MarketCalendarService.IST).minusDays(3)))attempt("AMFI","NAV_AUTO",false);
 }
 @Scheduled(fixedDelayString="${atlas.market.feeds.retry-poll-ms:60000}")
 public void retry(){
  if(!enabled)return;
  attempt("UPSTOX","MASTER_RETRY",true);
  attempt("AMFI","NAV_RETRY",true);
 }

 boolean attempt(String provider,String job,boolean retryOnly){
  if(!java.util.Set.of("UPSTOX","AMFI").contains(provider))throw new IllegalArgumentException("provider");
  UUID claim=UUID.randomUUID();
  Integer attempts=transactions.execute(tx->{
   var rows=jdbc.queryForList("""
     UPDATE public_feed_schedule SET
       attempts=CASE WHEN status IN ('RUNNING','RETRY') THEN LEAST(attempts+1,5) ELSE 1 END,
       interruptions=interruptions+CASE WHEN status='RUNNING' THEN 1 ELSE 0 END,
       status='RUNNING',claim_id=?,last_attempt_at=now(),
       lease_until=now()+interval '30 minutes',next_attempt_at=now()+interval '30 minutes'
     WHERE provider=? AND next_attempt_at<=now()
       AND (status<>'RUNNING' OR lease_until<=now())
       AND (NOT ? OR status IN ('RETRY','RUNNING'))
     RETURNING attempts
     """,claim,provider,retryOnly);
   if(rows.isEmpty())return null;
   int n=((Number)rows.getFirst().get("attempts")).intValue();
   jdbc.update("""
     UPDATE market_provider_runs SET status='FAILED',finished_at=now(),error_message='INTERRUPTED_CLAIM'
     WHERE provider=? AND status='RUNNING' AND claim_id IS NOT NULL
     """,provider);
   jdbc.update("""
     INSERT INTO market_provider_runs(provider,job_name,status,attempts,claim_id)
     VALUES (?,?,'RUNNING',?,?)
     """,provider,job,n,claim);
   return n;
  });
  if(attempts==null)return false;
  String status="SUCCESS",error=null;
  long delay=1800;
  try{
   int written="UPSTOX".equals(provider)?stocks.syncMaster():funds.refresh();
   if(written<=0)throw new IllegalStateException("EMPTY_VALIDATED_FEED");
  }catch(Exception ex){
   error=failureCode(ex);
   status=attempts>=5?"FAILED":"RETRY";
   delay=attempts>=5?3600:MarketIngestionScheduler.backoffSeconds(attempts,60,3600);
   if(ex instanceof FeedHttp.ProviderHttpException http)delay=Math.max(delay,http.retryAfterSeconds());
   if(ex instanceof InterruptedException)Thread.currentThread().interrupt();
  }
  final String completed=status,code=error;
  final long next=delay;
  transactions.executeWithoutResult(tx->{
   int changed=jdbc.update("""
     UPDATE public_feed_schedule SET status=?,claim_id=NULL,lease_until=NULL,
       last_success_at=CASE WHEN ? THEN now() ELSE last_success_at END,
       next_attempt_at=now()+(? * interval '1 second'),error_code=?
     WHERE provider=? AND status='RUNNING' AND claim_id=? AND lease_until>now()
     """,completed,"SUCCESS".equals(completed),next,code,provider,claim);
   if(changed==1)jdbc.update("""
     UPDATE market_provider_runs SET status=?,finished_at=now(),error_message=?,
       next_attempt_at=now()+(? * interval '1 second') WHERE claim_id=? AND status='RUNNING'
     """,completed,code,next,claim);
  });
  return true;
 }

 static String failureCode(Exception ex){
  if(ex instanceof FeedHttp.ProviderHttpException http){
   return switch(http.status()){
    case 429->"PROVIDER_RATE_LIMITED";
    case 401,403->"PROVIDER_ACCESS_REJECTED";
    default->"PROVIDER_HTTP_FAILED";
   };
  }
  if(ex instanceof java.io.IOException)return "PROVIDER_TRANSPORT_FAILURE";
  if(ex instanceof InterruptedException)return "INTERRUPTED_REQUEST";
  return "FEED_VALIDATION_OR_STORAGE_FAILED";
 }
}
