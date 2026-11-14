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
  private final VaultCrypto vault;
  @Value("${ATLAS_VAULT_KEY_VERSION:1}") int keyVersion;
  private final SecureRandom random=new SecureRandom();
  public BrokerVaultController(JdbcTemplate jdbc,@Value("${ATLAS_VAULT_MASTER_KEY:}") String key){
    this.jdbc=jdbc;
    if(key==null || key.isBlank()){vault=null;return;}
    vault=new VaultCrypto(key);
  }
  public record TokenInput(String accessToken,OffsetDateTime expiresAt){}
  @PostMapping("/token")
  public Map<String,Object> store(@RequestBody TokenInput input){
    if(vault==null)throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Vault not configured");
    if(input==null || input.accessToken()==null || input.accessToken().isBlank() ||
       input.accessToken().length()>8192 || input.expiresAt()==null ||
       !input.expiresAt().isAfter(OffsetDateTime.now()))
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid token or expiry");
    UUID user=AuthSecurity.currentUser();
    try {
      VaultCrypto.Sealed sealed=vault.encrypt(user,"UPSTOX",input.accessToken());
      jdbc.update(""" 
        INSERT INTO broker_credentials(user_id,broker_name,encrypted_access_token,iv_nonce,token_expires_at,key_version)
        VALUES (?,'UPSTOX',?,?,?,?) ON CONFLICT(user_id,broker_name) DO UPDATE SET
        encrypted_access_token=EXCLUDED.encrypted_access_token,
        iv_nonce=EXCLUDED.iv_nonce,key_version=EXCLUDED.key_version,token_expires_at=EXCLUDED.token_expires_at,updated_at=now()
        """,user,sealed.ciphertext(),sealed.nonce(),input.expiresAt(),keyVersion);
      return Map.of("stored",true,"broker","UPSTOX","expires_at",input.expiresAt().toString());
    }catch(Exception ex){
      throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,"Token encryption/storage failed");
    }
  }
}
