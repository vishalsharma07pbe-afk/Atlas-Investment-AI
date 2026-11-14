package com.trading.market;
import com.trading.data.DataImportService;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
@Service public class MarketIngestionScheduler {
 private final JdbcTemplate jdbc;private final DataImportService importer;private final MarketCalendarService calendar;
 @Value("${atlas.market.scheduler.enabled:false}") boolean enabled;
 @Value("${atlas.market.scheduler.max-attempts:5}") int maxAttempts;
 @Value("${atlas.market.scheduler.base-backoff-seconds:30}") long base;
 @Value("${atlas.market.scheduler.max-backoff-seconds:3600}") long cap;
 public MarketIngestionScheduler(JdbcTemplate jdbc,DataImportService importer,MarketCalendarService calendar){this.jdbc=jdbc;this.importer=importer;this.calendar=calendar;}
 public static long backoffSeconds(int attempt,long base,long cap){if(attempt<1||base<1||cap<1)throw new IllegalArgumentException();long v=base;for(int i=1;i<attempt;i++)v=v>cap/2?cap:Math.min(cap,v*2);return Math.min(v,cap);}
 @Scheduled(fixedDelayString="${atlas.market.scheduler.poll-ms:60000}")
 public void poll(){
  if(!enabled)return;
  for(int i=0;i<20;i++){
   List<Map<String,Object>> rows=jdbc.queryForList("UPDATE market_ingestion_queue SET state='RUNNING',locked_at=now(),attempts=attempts+1 WHERE id=(SELECT id FROM market_ingestion_queue WHERE state IN ('PENDING','RETRY') AND next_attempt_at<=now() ORDER BY next_attempt_at,id FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id,exchange_code,job_type,artifact_name,csv_payload,attempts");
   if(rows.isEmpty())break;Map<String,Object> r=rows.get(0);long id=((Number)r.get("id")).longValue();int attempt=((Number)r.get("attempts")).intValue();String type=(String)r.get("job_type");
   if(!type.equals("market-sessions")&&!calendar.isTradingDay((String)r.get("exchange_code"),LocalDate.now(MarketCalendarService.IST))){jdbc.update("UPDATE market_ingestion_queue SET state='RETRY',locked_at=NULL,next_attempt_at=now()+interval '1 hour' WHERE id=?",id);continue;}
   long exec=jdbc.queryForObject("INSERT INTO market_worker_executions(queue_id,job_name,status,attempt) VALUES (?,?,'RUNNING',?) RETURNING id",Long.class,id,type,attempt);
   try{importer.importCsv(type,(String)r.get("artifact_name"),(byte[])r.get("csv_payload"));jdbc.update("UPDATE market_ingestion_queue SET state='SUCCESS',completed_at=now(),locked_at=NULL,csv_payload=''::bytea WHERE id=?",id);jdbc.update("UPDATE market_worker_executions SET status='SUCCESS',finished_at=now() WHERE id=?",exec);}
   catch(Exception ex){boolean terminal=attempt>=maxAttempts;long delay=backoffSeconds(attempt,base,cap);String msg=Objects.toString(ex.getMessage(),"FAILED");msg=msg.substring(0,Math.min(500,msg.length()));jdbc.update("UPDATE market_ingestion_queue SET state=?,locked_at=NULL,last_error=?,next_attempt_at=now()+(? * interval '1 second') WHERE id=?",terminal?"FAILED":"RETRY",msg,delay,id);jdbc.update("UPDATE market_worker_executions SET status=?,error_message=?,finished_at=now() WHERE id=?",terminal?"FAILED":"RETRY",msg,exec);}
  }
 }
}
