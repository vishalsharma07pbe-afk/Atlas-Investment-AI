package com.trading.api;

import com.fasterxml.jackson.databind.JsonNode;
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
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private final ObjectMapper mapper = new ObjectMapper();
    @Value("${atlas.ai.proxy-enabled:false}")
    private boolean enabled;
    @Value("${atlas.ai.intelligence-url:http://intelligence:8000}")
    private String intelligenceUrl;
    @Value("${INTERNAL_SERVICE_TOKEN:}")
    private String serviceToken;

    private ResponseEntity<JsonNode> proxy(String path, String body) {
        if (!enabled || serviceToken == null || serviceToken.length() < 32)
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).build();
        // Destination is operator-configured, never taken from user input.
        try {
            HttpRequest.Builder builder=HttpRequest.newBuilder(URI.create(intelligenceUrl+path))
                .timeout(Duration.ofSeconds(30)).header("Accept","application/json")
                .header("X-Atlas-Service-Token",serviceToken);
            if (body == null) builder.GET();
            else builder.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(body));
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
        return proxy("/api/v1/ai/analyze/"+symbol,body.toString());
    }
}
