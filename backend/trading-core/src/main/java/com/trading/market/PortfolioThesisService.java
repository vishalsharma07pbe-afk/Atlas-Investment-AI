package com.trading.market;

import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.io.InputStream;
import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/** Join cached public company evidence to an already authenticated owner review. */
@Service
public class PortfolioThesisService {
 private final ObjectMapper json;
 private final FundHistoryResearchService funds;
 private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
 @Value("${INTERNAL_SERVICE_TOKEN:}") String serviceToken="";
 @Value("${atlas.ai.intelligence-url:http://intelligence:8000}") String intelligenceUrl;
 public PortfolioThesisService(ObjectMapper json,FundHistoryResearchService funds){this.json=json;this.funds=funds;}

 @SuppressWarnings("unchecked")
 public Map<String,Object> enrich(Map<String,Object> review){
  if(!(review.get("holdings") instanceof List<?> raw)||raw.isEmpty())return review;
  List<Map<String,Object>> holdings=new ArrayList<>();
  for(Object row:raw)if(row instanceof Map<?,?> m)holdings.add(new LinkedHashMap<>((Map<String,Object>)m));
  // Only explicit registry identities leave Spring, solely over the internal service route.
  List<Map<String,String>> identities=holdings.stream()
    .filter(h->"EQUITY".equals(h.get("asset_type"))&&h.get("isin") instanceof String isin&&isin.matches("IN[A-Z0-9]{10}")&&("NSE".equals(h.get("exchange"))||"BSE".equals(h.get("exchange"))))
    .map(h->Map.of("isin",(String)h.get("isin"),"exchange",(String)h.get("exchange"))).distinct().limit(100).toList();
  Map<String,JsonNode> evidence=identities.isEmpty()?Map.of():cached(identities);
  int fundReads=0;
  for(var h:holdings){
   if("EQUITY".equals(h.get("asset_type"))){
    String key=h.get("exchange")+":"+h.get("isin");
    if(evidence.containsKey(key))h.put("thesis_evidence",evidence.get(key));
   }else if("MUTUAL_FUND".equals(h.get("asset_type"))&&h.get("symbol") instanceof String code&&code.matches("[0-9]{1,18}")&&fundReads++<20){
    try{var historical=funds.holdingEvidence(Long.parseLong(code));if(historical!=null)h.put("fund_history_evidence",historical);}
    catch(RuntimeException ignored){/* Never fabricate missing fund evidence. */}
   }
   h.put("thesis_summary",PortfolioThesisSummary.summarize(h,json));
  }
  var result=new LinkedHashMap<>(review);result.put("holdings",holdings);
  result.put("thesis_review_count",holdings.stream().filter(h->h.get("thesis_summary") instanceof Map<?,?> m&&"REVIEW_EVIDENCE".equals(m.get("status"))).count());
  result.put("thesis_notice","Company and fund evidence is supplementary; the local holding-risk thresholds are unchanged. No external AI receives portfolio data.");
  return result;
 }

 private Map<String,JsonNode> cached(List<Map<String,String>> identities){
  if(serviceToken==null||serviceToken.length()<32)return Map.of();
  try{
   var request=HttpRequest.newBuilder(URI.create(intelligenceUrl+"/api/v1/internal/portfolio-thesis"))
    .timeout(Duration.ofSeconds(4)).header("Content-Type","application/json")
    .header("X-Atlas-Service-Token",serviceToken)
    .POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(Map.of("identities",identities)))).build();
   var response=client.send(request,HttpResponse.BodyHandlers.ofInputStream());
   try(InputStream body=response.body()){
    if(response.statusCode()!=200)return Map.of();
    byte[] bytes=body.readNBytes(2_000_001);if(bytes.length>2_000_000)return Map.of();
    JsonNode root=json.readTree(bytes),items=root.path("items");
    Map<String,JsonNode> result=new HashMap<>();
    for(var identity:identities){
     String key=identity.get("exchange")+":"+identity.get("isin");
     JsonNode item=items.path(key);
     if(item.isObject())result.put(key,item);
    }
    return result;
   }
  }catch(InterruptedException ex){Thread.currentThread().interrupt();return Map.of();}
  catch(Exception ex){return Map.of();}
 }
}
