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
import java.util.Locale;
import org.springframework.jdbc.core.JdbcTemplate;
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
  @Bean JwtTokens jwtTokens(@Value("${ATLAS_JWT_SECRET:}") String secret,JdbcTemplate jdbc){return new JwtTokens(secret,jdbc);}
  @Bean SecurityFilterChain security(HttpSecurity http,JwtTokens tokens) throws Exception {
    return http.csrf(c->c.disable()).httpBasic(c->c.disable()).formLogin(c->c.disable())
      .sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
      .exceptionHandling(e->e.authenticationEntryPoint((request,response,exception)->response.sendError(401)))
      .authorizeHttpRequests(a->a
        .requestMatchers(HttpMethod.POST,"/api/v1/auth/register","/api/v1/auth/login").permitAll()
        .requestMatchers("/api/v1/health","/actuator/health/**").permitAll()
        // Internal endpoints perform their own constant-time service-token check.
        .requestMatchers("/api/v1/internal/**").permitAll()
        .requestMatchers("/api/v1/**").authenticated()
        .anyRequest().denyAll())
      .addFilterBefore(new SameOriginCookieFilter(),BasicAuthenticationFilter.class)
      .addFilterBefore(new JwtFilter(tokens),BasicAuthenticationFilter.class).build();
  }
  /**
   * Cookie sessions are convenient for the same-origin dashboard, but disabling
   * Spring's form CSRF token must not make state-changing endpoints callable by
   * another website. Bearer-token clients remain usable across origins; this
   * guard applies only when the browser session cookie is present.
   */
  static class SameOriginCookieFilter extends OncePerRequestFilter {
    private static final java.util.Set<String> SAFE=java.util.Set.of("GET","HEAD","OPTIONS","TRACE");
    @Override protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain chain)
        throws ServletException,IOException{
      if(!SAFE.contains(req.getMethod()) && hasSessionCookie(req)){
        String fetchSite=req.getHeader("Sec-Fetch-Site");
        String origin=req.getHeader("Origin");
        if("cross-site".equalsIgnoreCase(fetchSite) || (origin!=null && !origin.equalsIgnoreCase(requestOrigin(req)))){
          res.sendError(HttpServletResponse.SC_FORBIDDEN,"Cross-origin cookie request rejected");
          return;
        }
      }
      chain.doFilter(req,res);
    }
    private static boolean hasSessionCookie(HttpServletRequest req){
      if(req.getCookies()==null)return false;
      for(var cookie:req.getCookies())if("ATLAS_SESSION".equals(cookie.getName()))return true;
      return false;
    }
    private static String requestOrigin(HttpServletRequest req){
      String proto=req.getHeader("X-Forwarded-Proto");
      if(proto==null||proto.isBlank())proto=req.getScheme();
      else proto=proto.split(",",2)[0].trim();
      String host=req.getHeader("Host");
      if(host==null||host.isBlank())host=req.getServerName()+((req.getServerPort()==80||req.getServerPort()==443)?"":":"+req.getServerPort());
      return proto.toLowerCase(Locale.ROOT)+"://"+host.toLowerCase(Locale.ROOT);
    }
  }
  public static UUID currentUser(){
    var auth=SecurityContextHolder.getContext().getAuthentication();
    if(auth==null || !(auth.getPrincipal() instanceof UUID id))
      throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.UNAUTHORIZED);
    return id;
  }
  public static class JwtTokens {
    private final byte[] key;
    private final JdbcTemplate jdbc;
    private final ObjectMapper json=new ObjectMapper();
    JwtTokens(String secret,JdbcTemplate jdbc){
      this.jdbc=jdbc;
      if(secret==null || secret.isBlank())throw new IllegalStateException("ATLAS_JWT_SECRET is required");
      byte[] decoded;
      try {decoded=Base64.getDecoder().decode(secret);}catch(IllegalArgumentException ex){throw new IllegalStateException("ATLAS_JWT_SECRET must be base64",ex);}
      if(decoded.length<32)throw new IllegalStateException("ATLAS_JWT_SECRET must decode to >=32 bytes");
      key=decoded;
    }
    public String issue(UUID user,long ttlSeconds){
      try {
        String head=enc("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        if(ttlSeconds<900 || ttlSeconds>2_592_000)throw new IllegalArgumentException("INVALID_SESSION_TTL");
        String body=enc(json.writeValueAsString(java.util.Map.of("sub",user.toString(),"exp",Instant.now().plusSeconds(ttlSeconds).getEpochSecond(),"iss","atlas-local")));
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
    private String sha(String token){
      try {return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));}
      catch(Exception ex){throw new IllegalStateException(ex);}
    }
    public void revoke(String token,UUID user){
      UUID valid=verify(token);
      if(!user.equals(valid))throw new IllegalArgumentException("INVALID_SESSION");
      jdbc.update("INSERT INTO revoked_jwt(token_sha256,user_id,expires_at) VALUES (?,?,now()+interval '15 minutes') ON CONFLICT DO NOTHING",sha(token),user);
      jdbc.update("DELETE FROM revoked_jwt WHERE expires_at < now()");
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
        UUID user=UUID.fromString(claims.path("sub").asText());
        Integer revoked=jdbc.queryForObject("SELECT count(*) FROM revoked_jwt WHERE token_sha256=?",Integer.class,sha(token));
        return revoked!=null && revoked>0 ? null : user;
      }catch(Exception ex){return null;}
    }
  }
  static class JwtFilter extends OncePerRequestFilter {
    private final JwtTokens tokens;
    JwtFilter(JwtTokens tokens){this.tokens=tokens;}
    @Override protected void doFilterInternal(HttpServletRequest req,HttpServletResponse res,FilterChain chain)
        throws ServletException,IOException{
      String header=req.getHeader("Authorization");
      String token=header!=null && header.startsWith("Bearer ") ? header.substring(7) : null;
      if(token==null && req.getCookies()!=null)for(var cookie:req.getCookies())
        if("ATLAS_SESSION".equals(cookie.getName())){token=cookie.getValue();break;}
      if(token!=null){
        UUID id=tokens.verify(token);
        if(id!=null)SecurityContextHolder.getContext().setAuthentication(
          new UsernamePasswordAuthenticationToken(id,null,java.util.List.of()));
      }
      chain.doFilter(req,res);
    }
  }
}
