package com.trading.api;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.util.*;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/broker/upstox")
public class BrokerVaultController {
  private final JdbcTemplate jdbc;
  private final SecretKeySpec masterKey;
  private final SecureRandom random=new SecureRandom();
  public BrokerVaultController(JdbcTemplate jdbc,@Value("${ATLAS_VAULT_MASTER_KEY:}") String key){
    this.jdbc=jdbc;
    if(key==null || key.isBlank()){masterKey=null;return;}
    byte[] raw;
    try {raw=Base64.getDecoder().decode(key);}catch(IllegalArgumentException ex){
      throw new IllegalStateException("Vault key must be base64",ex);
    }
    if(raw.length!=32)throw new IllegalStateException("Vault key must be 32 bytes");
    masterKey=new SecretKeySpec(raw,"AES");
    Arrays.fill(raw,(byte)0);
  }
  public record TokenInput(String accessToken,OffsetDateTime expiresAt){}
  @PostMapping("/token")
  public Map<String,Object> store(@RequestBody TokenInput input){
    if(masterKey==null)throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Vault not configured");
    if(input==null || input.accessToken()==null || input.accessToken().isBlank() ||
       input.accessToken().length()>8192 || input.expiresAt()==null ||
       !input.expiresAt().isAfter(OffsetDateTime.now()))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid token or expiry");
    UUID user=AuthSecurity.currentUser();
    byte[] nonce=new byte[12];random.nextBytes(nonce);
    try {
      Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.ENCRYPT_MODE,masterKey,new GCMParameterSpec(128,nonce));
      cipher.updateAAD((user.toString()+":UPSTOX").getBytes(StandardCharsets.UTF_8));
      byte[] ciphertext=cipher.doFinal(input.accessToken().getBytes(StandardCharsets.UTF_8));
      jdbc.update(""" 
        INSERT INTO broker_credentials(user_id,broker_name,encrypted_access_token,iv_nonce,token_expires_at)
        VALUES (?,'UPSTOX',?,?,?) ON CONFLICT(user_id,broker_name) DO UPDATE SET
        encrypted_access_token=EXCLUDED.encrypted_access_token,
        iv_nonce=EXCLUDED.iv_nonce,token_expires_at=EXCLUDED.token_expires_at,updated_at=now()
        """,user,ciphertext,nonce,input.expiresAt());
      return Map.of("stored",true,"broker","UPSTOX","expires_at",input.expiresAt().toString());
    }catch(Exception ex){
      throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,"Token encryption/storage failed");
    }
  }
}
