package com.trading.market;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.*;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Copy fresh shared market observations into existing owner-scoped valuations.
 * The internal service receives no holding identifiers, balances, or broker credentials.
 * The normal provider refresh remains responsible for history and delayed prices. */
@Service
public class PortfolioLiveValuationService {
 private final JdbcTemplate jdbc;
 private final ObjectMapper json;
 private final HttpClient http=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
 @Value("${atlas.live.intelligence-url:http://intelligence:8000}") String intelligenceUrl;
 @Value("${INTERNAL_SERVICE_TOKEN:}") String serviceToken;
 public PortfolioLiveValuationService(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}

 public Map<String,Object> refresh(UUID owner){
  if(serviceToken==null||serviceToken.length()<32)return Map.of("updated",0,"status","UNAVAILABLE");
  try{
   var request=HttpRequest.newBuilder(URI.create(intelligenceUrl+"/api/v1/internal/live/equity-snapshot"))
      .header("X-Atlas-Service-Token",serviceToken).timeout(Duration.ofSeconds(4)).GET().build();
   var response=http.send(request,HttpResponse.BodyHandlers.ofInputStream());
   try(var body=response.body()){
    if(response.statusCode()!=200)return Map.of("updated",0,"status","UNAVAILABLE");
    byte[] bytes=body.readNBytes(1_048_577);
    if(bytes.length>1_048_576)return Map.of("updated",0,"status","UNAVAILABLE");
    return apply(owner,json.readTree(bytes),Instant.now());
   }
  }catch(InterruptedException ex){Thread.currentThread().interrupt();return Map.of("updated",0,"status","UNAVAILABLE");}
   catch(Exception ex){return Map.of("updated",0,"status","UNAVAILABLE");}
 }

 Map<String,Object> apply(UUID owner,JsonNode snapshot,Instant now)throws Exception{
  if(!"AVAILABLE".equals(snapshot.path("status").asText())||!"UPSTOX_V3_STREAM".equals(snapshot.path("source").asText())
      ||!snapshot.path("items").isArray()||snapshot.path("items").size()>2000)
    return Map.of("updated",0,"status","UNAVAILABLE");
  var ticks=json.createArrayNode();Set<String> seen=new HashSet<>();
  for(JsonNode item:snapshot.path("items")){
   String key=item.path("instrument_key").asText("");
   if(!key.matches("(NSE_EQ|BSE_EQ)[|][A-Z0-9]{6,24}")||!seen.add(key)||!item.path("price").isNumber())continue;
   var price=item.path("price").decimalValue();if(price.signum()<=0||price.precision()>20||Math.abs(price.scale())>12)continue;
   Instant at;
   try{at=Instant.parse(item.path("as_of").asText());}catch(Exception invalid){continue;}
   if(at.isAfter(now)||at.isBefore(now.minusSeconds(15)))continue;
   var tick=ticks.addObject().put("instrument_key",key).put("price",price).put("observed_at",at.toString());
   if(item.path("previous_close").isNumber()&&item.path("previous_close").decimalValue().signum()>0
      &&item.path("previous_close").decimalValue().precision()<=20&&Math.abs(item.path("previous_close").decimalValue().scale())<=12)
      tick.put("previous_close",item.path("previous_close").decimalValue());
   else tick.putNull("previous_close");
  }
  if(ticks.isEmpty())return Map.of("updated",0,"status","UNAVAILABLE");
  int updated=jdbc.update("""
    WITH ticks AS (
      SELECT * FROM jsonb_to_recordset(?::jsonb) AS t(instrument_key text,price numeric,previous_close numeric,observed_at timestamptz)
    ), matched AS (
      SELECT h.id,h.user_id,h.symbol,m.instrument_key FROM personal_holdings h
      CROSS JOIN LATERAL (
        SELECT m.instrument_key FROM upstox_instrument_map m JOIN exchanges e ON e.code=m.exchange_code
        JOIN instruments i ON i.exchange_id=e.id AND i.symbol=m.trading_symbol AND i.isin=m.isin
        WHERE upper(m.trading_symbol)=upper(h.symbol) AND m.isin ~ '^IN[A-Z0-9]{10}$'
          AND e.code IN ('NSE','BSE') AND m.instrument_type IN ('EQ','EQUITY') AND i.active
          AND i.series='EQ' AND i.listing_status='ACTIVE' AND i.instrument_type IN ('EQ','EQUITY','STOCK')
          AND NOT EXISTS(SELECT 1 FROM instruments other JOIN exchanges venue ON venue.id=other.exchange_id
             WHERE venue.code IN ('NSE','BSE') AND upper(other.symbol)=upper(m.trading_symbol)
               AND other.active AND other.series='EQ' AND other.listing_status='ACTIVE'
               AND other.isin IS DISTINCT FROM m.isin)
        ORDER BY CASE WHEN e.code='NSE' THEN 0 ELSE 1 END,m.instrument_key LIMIT 1
      ) m WHERE h.user_id=? AND h.asset_type='EQUITY'
    )
    UPDATE personal_holdings h SET last_price=t.price,previous_close=t.previous_close,price_as_of=t.observed_at,updated_at=now()
    FROM matched m JOIN ticks t ON t.instrument_key=m.instrument_key
    WHERE h.id=m.id AND h.user_id=m.user_id AND h.symbol=m.symbol AND h.asset_type='EQUITY'
      AND t.observed_at<=now() AND t.observed_at>=now()-interval '15 seconds'
      AND (h.price_as_of IS NULL OR h.price_as_of<t.observed_at)
    """,json.writeValueAsString(ticks),owner);
  return Map.of("updated",updated,"status","AVAILABLE");
 }
}
