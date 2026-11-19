package com.trading.api;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** Authenticated browser SSE relay for the internal, read-only quote stream. */
@RestController
@RequestMapping("/api/v1/live")
public class MarketStreamController {
  private final HttpClient client=HttpClient.newBuilder()
      .version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(5)).build();

  @Value("${atlas.live.intelligence-url:http://intelligence:8000}")
  private String intelligenceUrl;
  @Value("${INTERNAL_SERVICE_TOKEN:}")
  private String serviceToken;

  @GetMapping(value="/market-indices",produces=MediaType.TEXT_EVENT_STREAM_VALUE)
  public SseEmitter indices(){
    AuthSecurity.currentUser();
    return relay("/api/v1/internal/live/market-indices");
  }

  @GetMapping(value="/instruments/{instrumentId}",produces=MediaType.TEXT_EVENT_STREAM_VALUE)
  public SseEmitter instrument(@PathVariable long instrumentId){
    AuthSecurity.currentUser();
    if(instrumentId<=0)throw new org.springframework.web.server.ResponseStatusException(
        org.springframework.http.HttpStatus.UNPROCESSABLE_ENTITY,"Invalid instrument ID");
    return relay("/api/v1/internal/live/instruments/"+instrumentId);
  }

  private SseEmitter relay(String path){
    if(serviceToken==null||serviceToken.length()<32)
      throw new org.springframework.web.server.ResponseStatusException(
          org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE,"Live stream is not configured");
    SseEmitter emitter=new SseEmitter(0L);
    AtomicBoolean closed=new AtomicBoolean(false);
    emitter.onCompletion(()->closed.set(true));
    emitter.onTimeout(()->closed.set(true));
    emitter.onError(error->closed.set(true));
    Thread.ofVirtual().name("atlas-market-sse").start(()->{
      try{
        HttpRequest request=HttpRequest.newBuilder(URI.create(intelligenceUrl+path))
            .version(HttpClient.Version.HTTP_1_1)
            .header("Accept",MediaType.TEXT_EVENT_STREAM_VALUE)
            .header("X-Atlas-Service-Token",serviceToken).GET().build();
        HttpResponse<Stream<String>> response=client.send(request,HttpResponse.BodyHandlers.ofLines());
        if(response.statusCode()!=200)throw new IllegalStateException("Internal stream rejected");
        try(Stream<String> lines=response.body()){
          String event="message";
          StringBuilder data=new StringBuilder();
          emitter.send(SseEmitter.event().reconnectTime(2_000));
          for(var iterator=lines.iterator();iterator.hasNext()&&!closed.get();){
            String line=iterator.next();
            if(line.startsWith("event:"))event=line.substring(6).trim();
            else if(line.startsWith("data:")){
              if(data.length()>0)data.append('\n');
              data.append(line.substring(5).trim());
              if(data.length()>524_288)throw new IllegalStateException("Internal stream event too large");
            }else if(line.isEmpty()&&data.length()>0){
              // Keep the upstream JSON as SSE text. Marking a Java String as
              // application/json can make some converters quote the complete
              // payload, forcing the browser to parse it twice.
              emitter.send(SseEmitter.event().name(event).data(data.toString()));
              event="message";data.setLength(0);
            }else if(line.startsWith(":")){
              emitter.send(SseEmitter.event().comment("keep-alive"));
            }
          }
        }
      }catch(Exception ignored){
        if(!closed.get())emitter.completeWithError(new IllegalStateException("Live market stream unavailable"));
      }finally{
        closed.set(true);
        emitter.complete();
      }
    });
    return emitter;
  }
}
