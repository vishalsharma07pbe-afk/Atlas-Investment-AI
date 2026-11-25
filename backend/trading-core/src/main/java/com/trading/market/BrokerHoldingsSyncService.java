package com.trading.market;

import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** Owner-consented read-only holdings reconciliation. The encrypted vault
 * remains the sole token source. One owner per pass; no operator token fallback. */
@Service
public class BrokerHoldingsSyncService {
  private final JdbcTemplate jdbc;
  private final UpstoxFeedService stocks;
  public BrokerHoldingsSyncService(JdbcTemplate jdbc,UpstoxFeedService stocks){
    this.jdbc=jdbc;this.stocks=stocks;
  }

  public Map<String,Object> preference(UUID owner,boolean enabled){
    jdbc.update("""
      INSERT INTO broker_holdings_sync(user_id,enabled) VALUES (?,?)
      ON CONFLICT(user_id) DO UPDATE SET enabled=EXCLUDED.enabled,status='PENDING',
        claim_id=NULL,lease_until=NULL,next_attempt_at=now(),failures=0,error_code=NULL
      WHERE broker_holdings_sync.enabled IS DISTINCT FROM EXCLUDED.enabled
      """,owner,enabled);
    return status(owner);
  }

  public Map<String,Object> status(UUID owner){
    return jdbc.queryForMap("""
      SELECT coalesce(s.enabled,false) AS enabled,
        CASE WHEN NOT coalesce(s.enabled,false) THEN 'DISABLED'
          WHEN b.user_id IS NULL THEN 'TOKEN_REQUIRED'
          WHEN b.token_expires_at<=now() THEN 'TOKEN_EXPIRED'
          WHEN s.status='RUNNING' AND s.lease_until>now() THEN 'RUNNING'
          WHEN s.credential_updated_at IS DISTINCT FROM b.updated_at THEN 'PENDING'
          WHEN s.status='RUNNING' THEN 'RECOVERY_PENDING'
          ELSE s.status END AS status,
        b.token_expires_at AS token_expires_at,
        s.last_attempt_at,s.last_success_at,
        CASE WHEN s.enabled AND b.token_expires_at>now() AND
          (s.credential_updated_at IS DISTINCT FROM b.updated_at OR
            s.status NOT IN ('REAUTH_REQUIRED','ACCESS_REJECTED','RUNNING'))
          THEN CASE WHEN s.credential_updated_at IS DISTINCT FROM b.updated_at THEN now() ELSE s.next_attempt_at END
          ELSE NULL END AS next_attempt_at,
        CASE WHEN s.enabled AND s.credential_updated_at=b.updated_at THEN s.error_code ELSE NULL END AS error_code
      FROM atlas_users u LEFT JOIN broker_holdings_sync s ON s.user_id=u.id
      LEFT JOIN broker_credentials b ON b.user_id=u.id AND b.broker_name='UPSTOX'
      WHERE u.id=?
      """,owner);
  }

  @Scheduled(initialDelayString="${atlas.broker.holdings.initial-ms:45000}",
             fixedDelayString="${atlas.broker.holdings.poll-ms:60000}")
  public void scheduled(){runOne();}

  public boolean runOne(){
    UUID claim=UUID.randomUUID();
    var claimed=jdbc.queryForList("""
      WITH due AS (
        SELECT s.user_id,b.updated_at AS credential_version
        FROM broker_holdings_sync s JOIN broker_credentials b
          ON b.user_id=s.user_id AND b.broker_name='UPSTOX'
        WHERE s.enabled AND b.token_expires_at>now()
          AND (s.status<>'RUNNING' OR s.lease_until<=now())
          AND (s.credential_updated_at IS DISTINCT FROM b.updated_at
            OR (s.status NOT IN ('REAUTH_REQUIRED','ACCESS_REJECTED') AND s.next_attempt_at<=now()))
        ORDER BY s.next_attempt_at,s.user_id LIMIT 1 FOR UPDATE OF s SKIP LOCKED
      )
      UPDATE broker_holdings_sync s SET status='RUNNING',claim_id=?,lease_until=now()+interval '10 minutes',
        next_attempt_at=now()+interval '10 minutes',last_attempt_at=now(),
        failures=CASE WHEN s.credential_updated_at IS DISTINCT FROM due.credential_version THEN 0 ELSE s.failures END,
        credential_updated_at=due.credential_version,error_code=NULL
      FROM due WHERE s.user_id=due.user_id RETURNING s.user_id
      """,claim);
    if(claimed.isEmpty())return false;
    UUID owner=(UUID)claimed.getFirst().get("user_id");
    String state="SUCCESS",error=null;
    try{
      stocks.syncClaimedHoldings(owner,claim);
    }catch(FeedHttp.ProviderHttpException ex){
      state=switch(ex.status()){case 401->"REAUTH_REQUIRED";case 403->"ACCESS_REJECTED";default->"RETRY";};
      error=ex.reason();
    }catch(Exception ex){
      state="RETRY";error="HOLDINGS_SYNC_UNAVAILABLE";
    }
    // Completion cannot overwrite a disabled, replaced or superseded claim.
    // A credential change makes the next attempt immediately eligible.
    jdbc.update("""
      UPDATE broker_holdings_sync SET status=?,error_code=?,claim_id=NULL,lease_until=NULL,
        last_success_at=CASE WHEN ?='SUCCESS' THEN now() ELSE last_success_at END,
        next_attempt_at=now()+CASE WHEN ?='SUCCESS' THEN interval '30 minutes'
          ELSE least(21600,300*power(2,least(failures,6))) * interval '1 second' END,
        failures=CASE WHEN ?='SUCCESS' THEN 0 ELSE least(failures+1,100) END
      WHERE user_id=? AND enabled AND claim_id=?
      """,state,error,state,state,state,owner,claim);
    return true;
  }
}
