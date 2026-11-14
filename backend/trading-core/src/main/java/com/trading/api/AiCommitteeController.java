package com.trading.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.jdbc.core.JdbcTemplate;
import java.math.BigDecimal;
import java.math.RoundingMode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/ai")
public class AiCommitteeController {
    private static final Pattern SYMBOL = Pattern.compile("[A-Z0-9._&-]{1,40}");
    private final HttpClient client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(3)).build();
    private final ObjectMapper mapper = new ObjectMapper();
    private final JdbcTemplate jdbc;
    public AiCommitteeController(JdbcTemplate jdbc){this.jdbc=jdbc;}
    @Value("${atlas.ai.proxy-enabled:false}")
    private boolean enabled;
    @Value("${atlas.ai.intelligence-url:http://intelligence:8000}")
    private String intelligenceUrl;
    @Value("${INTERNAL_SERVICE_TOKEN:}")
    private String serviceToken;

    private record AnalysisDto(@JsonProperty("symbol") String symbol,
                               @JsonProperty("market") String market,
                               @JsonProperty("price_change_pct") Double priceChangePct,
                               @JsonProperty("volume_change_pct") Double volumeChangePct,
                               @JsonProperty("technical_summary") String technicalSummary) {}

    private ResponseEntity<JsonNode> proxy(String path, String body) {
        if (!enabled || serviceToken == null || serviceToken.length() < 32)
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        // Destination is operator-configured, never taken from user input.
        try {
            HttpRequest.Builder builder=HttpRequest.newBuilder(URI.create(intelligenceUrl+path))
                .version(HttpClient.Version.HTTP_1_1)
                .timeout(Duration.ofSeconds(30)).header("Accept","application/json")
                .header("X-Atlas-Service-Token",serviceToken);
            if (body == null) builder.GET();
            else {
                if (body.isBlank()) return ResponseEntity.status(502).build();
                builder.header("Content-Type","application/json; charset=utf-8")
                    .POST(HttpRequest.BodyPublishers.ofString(body,java.nio.charset.StandardCharsets.UTF_8));
            }
            HttpResponse<String> response=client.send(builder.build(),HttpResponse.BodyHandlers.ofString());
            if (response.body().length()>262144) return ResponseEntity.status(502).build();
            JsonNode json=mapper.readTree(response.body());
            return ResponseEntity.status(response.statusCode()).body(json);
        } catch (Exception ex) {
            return ResponseEntity.status(502).build();
        }
    }

    @GetMapping("/providers/health")
    public ResponseEntity<JsonNode> health() {
        return proxy("/api/v1/ai/providers/health",null);
    }

    @PostMapping("/analyze/{symbol}")
    public ResponseEntity<JsonNode> analyze(@PathVariable String symbol,@RequestBody JsonNode body) {
        if (!SYMBOL.matcher(symbol).matches() || !body.isObject() || !body.has("symbol")
            || !symbol.equals(body.path("symbol").asText()))
            return ResponseEntity.unprocessableEntity().build();
        if (body.toString().length()>4096) return ResponseEntity.status(413).build();
        // Only aggregate relative weights; no quantities, prices, cost basis, or user IDs leave Spring.
        // Build an allowlisted request. Never forward arbitrary client fields or account data.
        ObjectNode safe=mapper.createObjectNode();
        safe.put("symbol",symbol);
        for(String field:java.util.List.of("market","sector","technical_summary","news_summary"))
          if(body.hasNonNull(field))safe.set(field,body.get(field));
        for(String field:java.util.List.of("price_change_pct","volume_change_pct"))
          if(body.hasNonNull(field))safe.set(field,body.get(field));
        // Reject forbidden fields instead of silently accepting hidden sensitive values.
        java.util.Set<String> allowed=java.util.Set.of("symbol","market","sector","technical_summary","news_summary","price_change_pct","volume_change_pct");
        var names=body.fieldNames();
        while(names.hasNext())if(!allowed.contains(names.next()))return ResponseEntity.unprocessableEntity().build();
        java.util.List<java.util.Map<String,Object>> positions=jdbc.queryForList(
          "SELECT symbol,quantity*last_price AS value FROM personal_holdings WHERE user_id=? AND last_price IS NOT NULL",
          AuthSecurity.currentUser());
        BigDecimal total=BigDecimal.ZERO,position=BigDecimal.ZERO;
        for(var row:positions){
          BigDecimal value=new BigDecimal(row.get("value").toString());
          total=total.add(value);
          if(symbol.equals(row.get("symbol")))position=position.add(value);
        }
        if(total.signum()>0){
          String pct=position.multiply(new BigDecimal("100")).divide(total,2,RoundingMode.HALF_UP).toPlainString();
          String existing=safe.path("technical_summary").asText("");
          String exposure="Portfolio position weight: "+pct+"% (priced holdings only).";
          if(existing.length()+exposure.length()+1<=600)safe.put("technical_summary",existing+" "+exposure);
        } else {
          String existing=safe.path("technical_summary").asText("");
          String exposure="Portfolio position weight: 0.0% (no priced holdings).";
          if(existing.length()+exposure.length()+1<=600)safe.put("technical_summary",existing+" "+exposure);
        }
        AnalysisDto dto = new AnalysisDto(symbol,
            safe.path("market").asText("NSE"),
            safe.hasNonNull("price_change_pct") ? safe.get("price_change_pct").asDouble() : null,
            safe.hasNonNull("volume_change_pct") ? safe.get("volume_change_pct").asDouble() : null,
            safe.path("technical_summary").asText(""));
        try {
            String serialized=mapper.writeValueAsString(dto);
            if (serialized.isBlank() || !symbol.equals(mapper.readTree(serialized).path("symbol").asText()))
                return ResponseEntity.status(502).build();
            return proxy("/api/v1/ai/analyze/"+symbol,serialized);
        } catch (com.fasterxml.jackson.core.JsonProcessingException ex) {
            return ResponseEntity.status(502).build();
        }
    }
}
