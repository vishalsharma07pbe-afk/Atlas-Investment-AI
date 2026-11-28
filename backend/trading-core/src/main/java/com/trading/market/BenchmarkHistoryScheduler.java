package com.trading.market;

import java.time.LocalDate;
import java.util.UUID;
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
  @Value("${ATLAS_SECTOR_BENCHMARKS_ENABLED:false}") boolean sectors;
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
    LocalDate end=DiscoveryHistoryScheduler.verifiedPriorSession(calendar,"NSE",today);
    if(end==null)return;
    refresh(end);
  }
  void refresh(LocalDate end){
    if(OperatorFeedCooldown.blocked(jdbc))return;
    if(!Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM data_sources WHERE source_code='UPSTOX' AND enabled)",Boolean.class)))return;
    // Keep the broad-market benchmark first. At most one provider call per
    // scheduler pass, including failures; per-index persisted claim is reused.
    if(refreshOne(end,BenchmarkHistoryService.KEY))return;
    if(sectors)for(String key:BenchmarkHistoryService.SECTOR_KEYS){
      if(OperatorFeedCooldown.blocked(jdbc)||refreshOne(end,key))return;
    }
  }
  boolean refreshOne(LocalDate end,String key){
    Long id=BenchmarkHistoryService.KEY.equals(key)?history.ensureIndex():history.ensureIndex(key);
    if(id==null)return false;
    // No early rollover for an already-current benchmark. Revisit depth/gaps
    // on the ordinary cooldown; stale successes can recover the new session.
    if(history.targetPresent(id,end) && Boolean.TRUE.equals(jdbc.queryForObject("""
      SELECT EXISTS(SELECT 1 FROM discovery_history_attempts
        WHERE instrument_id=? AND next_attempt_at>now())
      """,Boolean.class,id)))return false;
    UUID claim=UUID.randomUUID();
    if(DiscoveryHistoryScheduler.claimAttempt(jdbc,id,end,claim)!=1)return false;
    int written=0;
    try{
      if(OperatorFeedCooldown.blocked(jdbc)){
        DiscoveryHistoryScheduler.finishAttempt(jdbc,id,claim,false,0,15);
        return true;
      }
      written=BenchmarkHistoryService.KEY.equals(key)?history.refresh(id,token,end.minusDays(470),end):
        history.refresh(id,key,token,end.minusDays(470),end);
      boolean complete=written>0&&history.targetPresent(id,end);
      DiscoveryHistoryScheduler.finishAttempt(jdbc,id,claim,complete,written,complete?720:360);
      if(complete)OperatorFeedCooldown.recovered(jdbc);
    }catch(InterruptedException ex){
      Thread.currentThread().interrupt();
      DiscoveryHistoryScheduler.finishAttempt(jdbc,id,claim,false,written,15);
    }catch(Exception ex){
      // Never persist provider bodies, URLs or credentials.
      DiscoveryHistoryScheduler.finishAttempt(jdbc,id,claim,false,written,360);
      OperatorFeedCooldown.record(jdbc,ex);
    }
    return true;
  }
}
