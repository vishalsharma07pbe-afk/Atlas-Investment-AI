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
  List<Map<String,Object>> fundIdentities=new ArrayList<>();
  Set<Long> fundCodes=new LinkedHashSet<>();
  for(var h:holdings){
   if(!"MUTUAL_FUND".equals(h.get("asset_type"))||!(h.get("exact_scheme_code") instanceof Number n))continue;
   long code=n.longValue();
   if(code<100000||code>999999999||fundCodes.size()>=20||!fundCodes.add(code))continue;
   try{var identity=funds.holdingIdentity(code);if(identity!=null)fundIdentities.add(identity);}
   catch(RuntimeException ignored){/* Metadata unavailable. */}
  }
  JsonNode evidence=identities.isEmpty()&&fundIdentities.isEmpty()?json.createObjectNode():cached(identities,fundIdentities);
  Set<String> allowedFunds=new HashSet<>();
  for(var identity:fundIdentities)allowedFunds.add(String.valueOf(identity.get("scheme_code")));
  int fundReads=0;
  for(var h:holdings){
   if("EQUITY".equals(h.get("asset_type"))){
    String key=h.get("exchange")+":"+h.get("isin");
    if(evidence.path("items").path(key).isObject())h.put("thesis_evidence",evidence.path("items").path(key));
   }else if("MUTUAL_FUND".equals(h.get("asset_type"))&&h.get("symbol") instanceof String code&&code.matches("[0-9]{1,18}")&&fundReads++<20){
    try{var historical=funds.holdingEvidence(Long.parseLong(code));if(historical!=null)h.put("fund_history_evidence",historical);}
    catch(RuntimeException ignored){/* Never fabricate missing fund evidence. */}
    JsonNode fund=evidence.path("fund_items").path(code);
    if(allowedFunds.contains(code)&&fund.isObject()&&"SECONDARY_REPORTED_EVIDENCE".equals(fund.path("status").asText())&&code.equals(fund.path("disclosure").path("scheme_code").asText()))h.put("fund_thesis_evidence",fund);
   }
   if(h.get("holding_relative_strength") instanceof Map<?,?> rawRelative){
    var relative=new LinkedHashMap<String,Object>((Map<String,Object>)rawRelative);
    Object candidates=relative.remove("sector_candidates_internal");
    JsonNode thesis=json.valueToTree(h.get("thesis_evidence"));
    String sector=thesis.path("sector_benchmark_key").asText();
    if(BenchmarkHistoryService.SECTOR_KEYS.contains(sector)&&candidates instanceof Map<?,?> m&&m.get(sector)!=null)
      h.put("holding_sector_strength",m.get(sector));
    h.put("holding_relative_strength",relative);
   }
   h.put("thesis_summary",PortfolioThesisSummary.summarize(h,json));
   h.put("reassessment",PortfolioReassessment.holding(h,json,java.time.LocalDate.now(MarketCalendarService.IST)));
  }
  var result=new LinkedHashMap<>(review);result.put("holdings",holdings);
  result.put("portfolio_reassessment",PortfolioReassessment.synthesis(holdings,json));
  var diversification=PortfolioDiversification.summarize(holdings,json);
  diversification.put("look_through",PortfolioLookThrough.assess(holdings,json,java.time.Instant.now()));
  PortfolioLookThrough.stripWorkingWeights(holdings);
  result.put("diversification",diversification);
  result.put("opportunity_context",PortfolioOpportunityContext.compare(holdings,diversification,publicWatches(),json));
  result.put("thesis_review_count",holdings.stream().filter(h->h.get("thesis_summary") instanceof Map<?,?> m&&"REVIEW_EVIDENCE".equals(m.get("status"))).count());
  result.put("thesis_notice","Company and fund evidence is supplementary; the local holding-risk thresholds are unchanged. No external AI receives portfolio data.");
  return result;
 }

 private JsonNode publicWatches(){
  if(serviceToken==null||serviceToken.length()<32)return json.createObjectNode();
  try{
   var request=HttpRequest.newBuilder(URI.create(intelligenceUrl+"/api/v1/internal/portfolio-opportunities"))
    .timeout(Duration.ofSeconds(3)).header("X-Atlas-Service-Token",serviceToken).GET().build();
   var response=client.send(request,HttpResponse.BodyHandlers.ofInputStream());
   try(InputStream body=response.body()){
    if(response.statusCode()!=200)return json.createObjectNode();
    byte[] bytes=body.readNBytes(256_001);if(bytes.length>256_000)return json.createObjectNode();
    JsonNode data=json.readTree(bytes);
    return data!=null&&data.isObject()?data:json.createObjectNode();
   }
  }catch(InterruptedException ex){Thread.currentThread().interrupt();return json.createObjectNode();}
  catch(Exception ex){return json.createObjectNode();}
 }

 private JsonNode cached(List<Map<String,String>> identities,List<Map<String,Object>> fundIdentities){
  if(serviceToken==null||serviceToken.length()<32)return json.createObjectNode();
  try{
   var request=HttpRequest.newBuilder(URI.create(intelligenceUrl+"/api/v1/internal/portfolio-thesis"))
    .timeout(Duration.ofSeconds(4)).header("Content-Type","application/json")
    .header("X-Atlas-Service-Token",serviceToken)
    .POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(Map.of("identities",identities,"funds",fundIdentities)))).build();
   var response=client.send(request,HttpResponse.BodyHandlers.ofInputStream());
   try(InputStream body=response.body()){
    if(response.statusCode()!=200)return json.createObjectNode();
    byte[] bytes=body.readNBytes(2_000_001);if(bytes.length>2_000_000)return json.createObjectNode();
    JsonNode root=json.readTree(bytes);
    return root!=null&&root.isObject()?root:json.createObjectNode();
   }
  }catch(InterruptedException ex){Thread.currentThread().interrupt();return json.createObjectNode();}
  catch(Exception ex){return json.createObjectNode();}
 }
}
