package com.trading.api;

import java.util.*;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.Cookie;
import org.springframework.http.ResponseCookie;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
  private final JdbcTemplate jdbc;
  private final PasswordEncoder encoder;
  private final AuthSecurity.JwtTokens jwt;
  @Value("${ALLOW_REGISTRATION:false}") boolean allowRegistration;
  @Value("${ATLAS_SESSION_TTL_SECONDS:604800}") long configuredSessionTtlSeconds;
  @Value("${ATLAS_SESSION_COOKIE_SECURE:false}") boolean forceSecureCookie;
  AuthController(JdbcTemplate jdbc,PasswordEncoder encoder,AuthSecurity.JwtTokens jwt){
    this.jdbc=jdbc;this.encoder=encoder;this.jwt=jwt;
  }
  public record Credentials(String email,String password){}
  @PostMapping("/register")
  public Map<String,Object> register(@RequestBody Credentials request){
    if(!allowRegistration)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Registration disabled");
    String email=validEmail(request.email());
    if(request.password()==null || request.password().length()<12 || request.password().length()>128)
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Password must be 12-128 characters");
    UUID id=UUID.randomUUID();
    try {jdbc.update("INSERT INTO atlas_users(id,email,password_hash,role) VALUES (?,?,?,'USER')",
      id,email,encoder.encode(request.password()));}
    catch(org.springframework.dao.DuplicateKeyException ex){throw new ResponseStatusException(HttpStatus.CONFLICT,"Email already registered");}
    return Map.of("id",id,"email",email);
  }
  private String validEmail(String raw){
    if(raw==null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
    String email=raw.trim().toLowerCase(Locale.ROOT);
    if(email.length()>254 || !email.matches("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid email");
    return email;
  }
  @PostMapping("/login")
  public Map<String,Object> login(@RequestBody Credentials request,HttpServletRequest http,HttpServletResponse response){
    String email=validEmail(request.email());
    String emailHash=hash(email),ipHash=hash(http.getRemoteAddr());
    Integer failures=jdbc.queryForObject("SELECT count(*) FROM auth_login_failures WHERE (email_hash=? OR ip_hash=?) AND attempted_at>now()-interval '1 minute'",Integer.class,emailHash,ipHash);
    if(failures!=null && failures>=5)throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"Try again later");
    var users=jdbc.queryForList("SELECT id,password_hash FROM atlas_users WHERE email=?",email);
    if(users.size()!=1 || request.password()==null ||
       !encoder.matches(request.password(),(String)users.get(0).get("password_hash"))) {
      jdbc.update("INSERT INTO auth_login_failures(email_hash,ip_hash) VALUES (?,?)",emailHash,ipHash);
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED,"Invalid credentials");
    }
    UUID id=(UUID)users.get(0).get("id");
    long sessionTtlSeconds=Math.max(900,Math.min(configuredSessionTtlSeconds,2_592_000));
    String token=jwt.issue(id,sessionTtlSeconds);
    response.addHeader("Set-Cookie",sessionCookie(token,sessionTtlSeconds,forceSecureCookie||http.isSecure()).toString());
    return Map.of("access_token",token,"token_type","Bearer","expires_in",sessionTtlSeconds);
  }
  private static String hash(String value){
    try {return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}
    catch(Exception ex){throw new IllegalStateException(ex);}
  }
  @PostMapping("/logout")
  public Map<String,Boolean> logout(@org.springframework.web.bind.annotation.RequestHeader(value="Authorization",required=false) String authorization,
                                    HttpServletRequest request,HttpServletResponse response){
    String token=authorization!=null && authorization.startsWith("Bearer ") ? authorization.substring(7) : cookieToken(request);
    if(token==null)throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    jwt.revoke(token,AuthSecurity.currentUser());
    response.addHeader("Set-Cookie",sessionCookie("",0,forceSecureCookie||request.isSecure()).toString());
    return Map.of("logged_out",true);
  }
  private static String cookieToken(HttpServletRequest request){
    Cookie[] cookies=request.getCookies();if(cookies==null)return null;
    for(Cookie cookie:cookies)if("ATLAS_SESSION".equals(cookie.getName()))return cookie.getValue();
    return null;
  }
  private static ResponseCookie sessionCookie(String token,long maxAge,boolean secure){
    return ResponseCookie.from("ATLAS_SESSION",token).httpOnly(true).secure(secure).sameSite("Strict")
      .path("/").maxAge(maxAge).build();
  }
  @GetMapping("/me")
  public Map<String,Object> me(){
    UUID id=AuthSecurity.currentUser();
    var rows=jdbc.queryForList("SELECT id,email,role FROM atlas_users WHERE id=?",id);
    if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    return rows.get(0);
  }
}
