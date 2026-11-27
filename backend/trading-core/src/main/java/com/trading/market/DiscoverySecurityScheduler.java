package com.trading.market;

import com.fasterxml.jackson.databind.*;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Public Upstox suspended-instrument observations; no account API or order permissions.
 * A missing listing is never represented as proof that it is unrestricted.
 */
@Service
public class DiscoverySecurityScheduler {
 static final String SOURCE="https://assets.upstox.com/market-quote/instruments/exchange/suspended-instrument.json.gz";
 private final JdbcTemplate db;
 private final FeedHttp http;
 private final TransactionTemplate transaction;
 private final ObjectMapper json=new ObjectMapper();
 @Value("${ATLAS_DISCOVERY_QUOTE_SCREEN_ENABLED:false}") boolean enabled;
 @Value("${MARKET_DATA_USAGE_RIGHTS_CONFIRMED:false}") boolean rights;
 public DiscoverySecurityScheduler(JdbcTemplate db,FeedHttp http,TransactionTemplate transaction){
  this.db=db;this.http=http;this.transaction=transaction;
 }
 record Listing(String exchange,String isin,String key){}
 @Scheduled(initialDelayString="${atlas.discovery.security.initial-ms:90000}",fixedDelayString="${atlas.discovery.security.poll-ms:21600000}")
 public void scheduled(){
  if(!enabled||!rights)return;
  try{
   Instant retrieved=Instant.now();
   var rows=parse(json.readTree(http.get(SOURCE,null,12_000_000)));
   transaction.executeWithoutResult(status->{
    db.execute("LOCK TABLE discovery_suspension_snapshot IN EXCLUSIVE MODE");
    if(Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM discovery_suspension_snapshot WHERE retrieved_at>?)",Boolean.class,Timestamp.from(retrieved))))return;
    db.update("DELETE FROM discovery_suspended_listing");
    db.batchUpdate("INSERT INTO discovery_suspended_listing(exchange,isin,instrument_key) VALUES (?,?,?)",
      rows.stream().map(r->new Object[]{r.exchange(),r.isin(),r.key()}).toList());
    db.update("""
      INSERT INTO discovery_suspension_snapshot(singleton,retrieved_at,record_count) VALUES (true,?,?)
      ON CONFLICT(singleton) DO UPDATE SET retrieved_at=excluded.retrieved_at,record_count=excluded.record_count
      """,Timestamp.from(retrieved),rows.size());
   });
  }catch(InterruptedException ex){Thread.currentThread().interrupt();}
  catch(Exception ex){
   // Retain the last valid snapshot; positive suspensions continue to block
   // discovery until a newer valid snapshot replaces them.
   // Never log provider bodies or credential-bearing errors.
  }
 }
 static Set<Listing> parse(JsonNode root){
  if(root==null||!root.isArray()||root.size()>50000)throw new IllegalArgumentException("INVALID_SUSPENSION_ENVELOPE");
  Set<Listing> result=new HashSet<>();
  for(JsonNode item:root){
   if(!item.isObject())throw new IllegalArgumentException("INVALID_SUSPENSION_RECORD");
   String exchange=item.path("exchange").asText(""),segment=item.path("segment").asText(""),isin=item.path("isin").asText(""),key=item.path("instrument_key").asText("");
   if(!Set.of("NSE","BSE").contains(exchange)||!segment.equals(exchange+"_EQ")||!isin.startsWith("INE"))continue;
   if(!UpstoxFeedService.validEquityIdentity(exchange,key,isin)||
      (key.matches("BSE_EQ[|][0-9]{1,10}")&&!key.equals("BSE_EQ|"+item.path("exchange_token").asText(""))))
      throw new IllegalArgumentException("INVALID_SUSPENSION_IDENTITY");
   if(!result.add(new Listing(exchange,isin,key)))throw new IllegalArgumentException("DUPLICATE_SUSPENSION_IDENTITY");
  }
  if(!root.isEmpty()&&result.isEmpty())throw new IllegalArgumentException("NO_SUPPORTED_SUSPENSION_RECORDS");
  return result;
 }
}
