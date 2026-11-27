package com.trading.market;

import java.time.LocalDate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Reuses discovery attempt persistence, with a separate INDEX identity. */
@Service
public class BenchmarkHistoryScheduler {
  private final JdbcTemplate jdbc;
  private final BenchmarkHistoryService history;
  private final MarketCalendarService calendar;
  @Value("${ATLAS_BENCHMARK_HISTORY_ENABLED:false}") boolean enabled;
  @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean rights;
  @Value("${MARKET_DATA_ENTITLEMENT_CONFIRMED:false}") boolean entitlement;
  @Value("${UPSTOX_ACCESS_TOKEN:}") String token="";
  public BenchmarkHistoryScheduler(JdbcTemplate jdbc,BenchmarkHistoryService history,MarketCalendarService calendar){
    this.jdbc=jdbc;this.history=history;this.calendar=calendar;
  }
  @Scheduled(initialDelayString="${atlas.benchmark.history.initial-ms:120000}",
             fixedDelayString="${atlas.benchmark.history.poll-ms:300000}")
  public void scheduled(){
    if(!enabled||!rights||!entitlement||token.isBlank())return;
    LocalDate today=LocalDate.now(MarketCalendarService.IST);
    LocalDate end;
    try{end=calendar.lastTradingDay("NSE",today);}catch(IllegalStateException ex){return;}
    if(end.isBefore(today.minusDays(7)))return;
    refresh(end);
  }
  void refresh(LocalDate end){
    if(OperatorFeedCooldown.blocked(jdbc))return;
    if(!Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM data_sources WHERE source_code='UPSTOX' AND enabled)",Boolean.class)))return;
    Long id=history.ensureIndex();
    if(id==null)return;
    int claimed=jdbc.update("""
      INSERT INTO discovery_history_attempts(instrument_id,attempted_at,next_attempt_at,status)
      VALUES (?,now(),now()+interval '6 hours','RUNNING')
      ON CONFLICT(instrument_id) DO UPDATE SET attempted_at=now(),
        next_attempt_at=now()+interval '6 hours',status='RUNNING'
      WHERE discovery_history_attempts.next_attempt_at<=now()
      """,id);
    if(claimed!=1)return;
    int written=0;
    try{written=history.refresh(id,token,end.minusDays(470),end);}catch(Exception ex){
      // Never persist provider bodies, URLs or credentials.
      OperatorFeedCooldown.record(jdbc,ex);
    }
    if(written>0){
      OperatorFeedCooldown.recovered(jdbc);
      jdbc.update("""
      UPDATE discovery_history_attempts SET status='SUCCESS',rows_written=?,
        next_attempt_at=now()+interval '12 hours' WHERE instrument_id=?
      """,written,id);
    }else jdbc.update("""
      UPDATE discovery_history_attempts SET status='FAILED',rows_written=0,
        next_attempt_at=now()+interval '6 hours' WHERE instrument_id=?
      """,id);
  }
}
