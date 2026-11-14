package com.trading.market;
import java.net.*;
import java.net.http.*;
import java.time.Duration;
import java.util.zip.GZIPInputStream;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.springframework.stereotype.Service;
@Service public class FeedHttp {
 private final HttpClient client=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).followRedirects(HttpClient.Redirect.NORMAL).build();
 public byte[] get(String url,String token,int maxBytes) throws Exception{
  URI uri=URI.create(url);
  if(!"https".equals(uri.getScheme()))throw new IllegalArgumentException("HTTPS required");
  HttpRequest.Builder b=HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(25)).header("Accept","application/json,text/plain,*/*").GET();
  if(token!=null)b.header("Authorization","Bearer "+token);
  HttpResponse<InputStream> response=client.send(b.build(),HttpResponse.BodyHandlers.ofInputStream());
  try(InputStream raw=response.body()){
   if(response.statusCode()!=200)throw new IOException("Provider HTTP "+response.statusCode());
   InputStream stream=url.endsWith(".gz")?new GZIPInputStream(raw):raw;
   try(stream){byte[] bytes=stream.readNBytes(maxBytes+1);if(bytes.length>maxBytes)throw new IOException("Provider response too large");return bytes;}
  }
 }
 public String text(String url,String token,int maxBytes)throws Exception{return new String(get(url,token,maxBytes),StandardCharsets.UTF_8);}
}
