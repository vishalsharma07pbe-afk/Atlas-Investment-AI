package com.trading.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Base64;
import java.util.UUID;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

@Configuration
public class AuthSecurity {
  @Bean PasswordEncoder passwordEncoder(){return new BCryptPasswordEncoder(12);}
  @Bean JwtTokens jwtTokens(@Value("${ATLAS_JWT_SECRET:}") String secret){return new JwtTokens(secret);}
  @Bean SecurityFilterChain security(HttpSecurity http,JwtTokens tokens) throws Exception {
    return http.csrf(c->c.disable()).httpBasic(c->c.disable()).formLogin(c->c.disable())
      .sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
      .exceptionHandling(e->e.authenticationEntryPoint((request,response,exception)->response.sendError(401)))
      .authorizeHttpRequests(a->a
        .requestMatchers(HttpMethod.POST,"/api/v1/auth/register","/api/v1/auth/login").permitAll()
        .requestMatchers("/api/v1/health","/actuator/health/**").permitAll()
        .requestMatchers("/api/v1/**").authenticated()
        .anyRequest().denyAll())
      .addFilterBefore(new JwtFilter(tokens),BasicAuthenticationFilter.class).build();
  }
  public static UUID currentUser(){
    var auth=SecurityContextHolder.getContext().getAuthentication();
    if(auth==null || !(auth.getPrincipal() instanceof UUID id))
      throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.UNAUTHORIZED);
    return id;
  }
  public static class JwtTokens {
    private final byte[] key;
    private final ObjectMapper json=new ObjectMapper();
    JwtTokens(String secret){
      if(secret==null || secret.isBlank()){key=null;return;}
      byte[] decoded;
      try {decoded=Base64.getDecoder().decode(secret);}catch(IllegalArgumentException ex){throw new IllegalStateException("ATLAS_JWT_SECRET must be base64",ex);}
      if(decoded.length<32)throw new IllegalStateException("ATLAS_JWT_SECRET must decode to >=32 bytes");
      key=decoded;
    }
    public String issue(UUID user){
      if(key==null)throw new IllegalStateException("JWT signing secret not configured");
      try {
        String head=enc("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        String body=enc(json.writeValueAsString(java.util.Map.of("sub",user.toString(),"exp",Instant.now().plusSeconds(900).getEpochSecond(),"iss","atlas-local")));
        String data=head+"."+body;
        return data+"."+Base64.getUrlEncoder().withoutPadding().encodeToString(sign(data));
      }catch(Exception ex){throw new IllegalStateException("JWT signing failed",ex);}
    }
    private String enc(String s){return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
    private byte[] sign(String s)throws Exception{
      Mac mac=Mac.getInstance("HmacSHA256");
      mac.init(new SecretKeySpec(key,"HmacSHA256"));
      return mac.doFinal(s.getBytes(StandardCharsets.US_ASCII));
    }
    public UUID verify(String token){
      if(key==null || token==null || token.length()>4096)return null;
      try {
        String[] parts=token.split("\\.",-1);
        if(parts.length!=3)return null;
        String data=parts[0]+"."+parts[1];
        if(!MessageDigest.isEqual(sign(data),Base64.getUrlDecoder().decode(parts[2])))return null;
        JsonNode header=json.readTree(Base64.getUrlDecoder().decode(parts[0]));
        JsonNode claims=json.readTree(Base64.getUrlDecoder().decode(parts[1]));
        if(!"HS256".equals(header.path("alg").asText()) || !"atlas-local".equals(claims.path("iss").asText())
           || claims.path("exp").asLong(0)<=Instant.now().getEpochSecond())return null;
        return UUID.fromString(claims.path("sub").asText());
      }catch(Exception ex){return null;}
    }
  }
  static class JwtFilter extends OncePerRequestFilter {
    private final JwtTokens tokens;
    JwtFilter(JwtTokens tokens){this.tokens=tokens;}
    @Override protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain chain)
        throws ServletException,IOException{
      String header=req.getHeader("Authorization");
      if(header!=null && header.startsWith("Bearer ")){
        UUID id=tokens.verify(header.substring(7));
        if(id!=null)SecurityContextHolder.getContext().setAuthentication(
          new UsernamePasswordAuthenticationToken(id,null,java.util.List.of()));
      }
      chain.doFilter(req,res);
    }
  }
}
