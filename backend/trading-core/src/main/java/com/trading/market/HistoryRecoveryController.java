package com.trading.market;

import java.time.*;
import java.util.*;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

/** Authenticated, aggregate-only diagnostics. Never calls a provider or a private portfolio. */
@RestController
@RequestMapping("/api/v1/data-health")
public class HistoryRecoveryController {
  private final JdbcTemplate jdbc;
  private final DiscoveryHistoryScheduler scheduler;
  public HistoryRecoveryController(JdbcTemplate jdbc,DiscoveryHistoryScheduler scheduler){
    this.jdbc=jdbc;this.scheduler=scheduler;
  }

  @GetMapping("/history-recovery")
  @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ,timeout=20)
  public ResponseEntity<Map<String,Object>> historyRecovery(){
    return ResponseEntity.ok().cacheControl(CacheControl.noStore())
      .body(progress(LocalDate.now(MarketCalendarService.IST)));
  }

  Map<String,Object> progress(LocalDate today){
    var exchanges=new ArrayList<Map<String,Object>>();
    boolean blocked=OperatorFeedCooldown.blocked(jdbc);
    boolean configured=scheduler.enabled&&scheduler.usageRights&&scheduler.entitlement&&!scheduler.accessToken.isBlank();
    for(String exchange:List.of("NSE","BSE")){
      LocalDate target=scheduler.verifiedPriorSession(exchange,today);
      LocalDate floor=target==null?null:target.minusMonths(DiscoveryHistoryScheduler.BACKFILL_MONTHS);
      var row=new LinkedHashMap<String,Object>(jdbc.queryForMap("""
        WITH params AS (SELECT CAST(? AS date) target,CAST(? AS date) floor,CAST(? AS integer) depth),
        listings AS (
          SELECT u.instrument_id,u.isin,p.target,p.depth,a.status,a.target_session,a.attempted_at,a.next_attempt_at,
            coalesce(q.security_state,'UNKNOWN')='SUSPENDED_REPORTED' suspended,
            coalesce(h.has_adjusted,false) protected_adjusted,
            coalesce(h.current_candle,false) current_candle,h.daily_dates,h.adjusted_dates
          FROM discovery_quote_universe u CROSS JOIN params p
          LEFT JOIN discovery_history_attempts a ON a.instrument_id=u.instrument_id
          LEFT JOIN discovery_security_context q ON q.instrument_id=u.instrument_id AND q.instrument_key=u.instrument_key AND q.isin=u.isin
          CROSS JOIN LATERAL (
            SELECT bool_or(c.adjustment_status='ADJUSTED') has_adjusted,
              bool_or(c.candle_time>=p.target::timestamp AT TIME ZONE 'Asia/Kolkata'
                AND c.candle_time<(p.target+1)::timestamp AT TIME ZONE 'Asia/Kolkata') current_candle,
              count(DISTINCT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date)
                FILTER (WHERE c.candle_time>=p.floor::timestamp AT TIME ZONE 'Asia/Kolkata'
                  AND c.candle_time<(p.target+1)::timestamp AT TIME ZONE 'Asia/Kolkata') daily_dates,
              count(DISTINCT (c.candle_time AT TIME ZONE 'Asia/Kolkata')::date)
                FILTER (WHERE c.adjustment_status='ADJUSTED'
                  AND c.candle_time>=p.floor::timestamp AT TIME ZONE 'Asia/Kolkata'
                  AND c.candle_time<(p.target+1)::timestamp AT TIME ZONE 'Asia/Kolkata') adjusted_dates
            FROM market_candles c WHERE c.instrument_id=u.instrument_id AND c.timeframe='1d'
              AND c.is_complete AND c.quality_status IN ('VALIDATED_MANUAL','PROVIDER_VALIDATED')
          ) h WHERE u.exchange=?
        ), classified AS (
          SELECT *, NOT suspended AND NOT protected_adjusted AND NOT current_candle AS recoverable,
            (target_session IS NULL OR target_session<=target)
              AND (next_attempt_at IS NULL OR next_attempt_at<=now()
                OR (status='SUCCESS' AND (target_session IS NULL OR target_session<target))) AS claimable
          FROM listings
        )
        SELECT count(*) AS mapped_listings,count(DISTINCT isin) AS mapped_companies,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN count(*) FILTER (WHERE current_candle) END AS current_listings,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN count(*) FILTER (WHERE daily_dates>=depth) END AS deep_listings,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN count(*) FILTER (WHERE adjusted_dates>=depth) END AS adjusted_depth_listings,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN count(*) FILTER (WHERE recoverable) END AS recoverable_missing,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN count(*) FILTER (WHERE recoverable AND claimable) END AS due_missing,
          count(*) FILTER (WHERE status='RUNNING' AND next_attempt_at>now()) AS active_claims,
          count(*) FILTER (WHERE status='RUNNING' AND next_attempt_at<=now()) AS expired_claims,
          count(*) FILTER (WHERE status='FAILED') AS failed_last_attempts,
          count(*) FILTER (WHERE status IS NULL) AS never_attempted,
          count(*) FILTER (WHERE suspended) AS suspended_listings,
          count(*) FILTER (WHERE protected_adjusted) AS protected_adjusted_listings,
          max(attempted_at) AS last_attempt_at,
          max(attempted_at) FILTER (WHERE status='SUCCESS') AS last_successful_attempt_started_at,
          CASE WHEN (SELECT target FROM params) IS NOT NULL THEN
            min(next_attempt_at) FILTER (WHERE recoverable AND NOT claimable AND next_attempt_at>now()) END AS next_deferred_missing_attempt_at
        FROM classified
        """,target,floor,DiscoveryHistoryScheduler.REQUIRED_DAILY_CANDLES,exchange));
      row.put("exchange",exchange);
      row.put("target_session",target==null?null:target.toString());
      row.put("calendar_status",target==null?"UNVERIFIED":"VERIFIED_PRIOR_REGULAR_SESSION");
      exchanges.add(row);
    }
    Map<String,Object> out=new LinkedHashMap<>();
    out.put("generated_at",Instant.now().toString());
    out.put("configured",configured);
    out.put("provider_blocked",blocked);
    out.put("provider_blocked_until",jdbc.queryForObject("""
      SELECT max(blocked_until) FROM operator_feed_cooldown WHERE scope='UPSTOX_OPERATOR' AND blocked_until>now()
      """,java.sql.Timestamp.class));
    out.put("distinct_mapped_companies",jdbc.queryForObject("SELECT count(DISTINCT isin) FROM discovery_quote_universe",Long.class));
    out.put("depth_target",DiscoveryHistoryScheduler.REQUIRED_DAILY_CANDLES);
    out.put("exchanges",exchanges);
    return out;
  }
}
