package com.trading.market;
import java.time.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
@Service public class FeedRefreshScheduler {
 private final JdbcTemplate jdbc;private final UpstoxFeedService stocks;private final AmfiFeedService funds;private final MarketCalendarService calendar;
 @Value("${atlas.market.feeds.enabled:false}") boolean enabled;
 public FeedRefreshScheduler(JdbcTemplate jdbc,UpstoxFeedService stocks,AmfiFeedService funds,MarketCalendarService calendar){this.jdbc=jdbc;this.stocks=stocks;this.funds=funds;this.calendar=calendar;}
 @Scheduled(cron="0 10 8 * * MON-FRI",zone="Asia/Kolkata") public void master(){if(enabled&&calendar.isTradingDay("NSE",LocalDate.now(MarketCalendarService.IST)))run("UPSTOX","MASTER",()->stocks.syncMaster());}
 @Scheduled(cron="0 0 22 * * MON-FRI",zone="Asia/Kolkata") public void amfi(){if(enabled)run("AMFI","NAV",()->funds.refresh());}
 private void run(String provider,String job,Checked task){
  long id=jdbc.queryForObject("INSERT INTO market_provider_runs(provider,job_name,status) VALUES (?,?,'RUNNING') RETURNING id",Long.class,provider,job);
  try{task.execute();jdbc.update("UPDATE market_provider_runs SET status='SUCCESS',finished_at=now() WHERE id=?",id);}
  catch(Exception ex){jdbc.update("UPDATE market_provider_runs SET status='RETRY',attempts=1,next_attempt_at=now()+interval '30 seconds',error_message=?,finished_at=now() WHERE id=?",ex.getClass().getSimpleName(),id);}
 }
 @Scheduled(fixedDelayString="${atlas.market.feeds.retry-poll-ms:60000}") public void retry(){
  if(!enabled)return;
  for(var row:jdbc.queryForList("SELECT id,provider,job_name,attempts FROM market_provider_runs WHERE status='RETRY' AND next_attempt_at<=now() ORDER BY id LIMIT 10")){
   long id=((Number)row.get("id")).longValue();int attempts=((Number)row.get("attempts")).intValue();
   try{if("UPSTOX".equals(row.get("provider")))stocks.syncMaster();else funds.refresh();jdbc.update("UPDATE market_provider_runs SET status='SUCCESS',finished_at=now() WHERE id=?",id);}
   catch(Exception ex){int next=attempts+1;long delay=MarketIngestionScheduler.backoffSeconds(next,30,3600);jdbc.update("UPDATE market_provider_runs SET status=?,attempts=?,next_attempt_at=now()+(? * interval '1 second'),error_message=? WHERE id=?",next>=5?"FAILED":"RETRY",next,delay,ex.getClass().getSimpleName(),id);}
  }
 }
 interface Checked{void execute()throws Exception;}
}
