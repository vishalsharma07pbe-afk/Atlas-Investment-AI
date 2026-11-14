package com.trading.api;

import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/** Strict key-version selection. No trial-decrypt fallback to unrelated keys. */
@Service
public class VersionedVaultReader {
  private final JdbcTemplate jdbc;
  private final VaultCrypto current,previous;
  private final int version;
  public VersionedVaultReader(JdbcTemplate jdbc,
      @Value("${ATLAS_VAULT_MASTER_KEY:}") String master,
      @Value("${ATLAS_VAULT_PREVIOUS_KEY:}") String old,
      @Value("${ATLAS_VAULT_KEY_VERSION:1}") int version){
    this.jdbc=jdbc;this.version=version;
    if(version<1)throw new IllegalStateException("Invalid vault version");
    this.current=master.isBlank()?null:new VaultCrypto(master);
    this.previous=old.isBlank()?null:new VaultCrypto(old);
  }
  /** Internal use only. Never expose this method through a controller. */
  public String decrypt(UUID user,String broker){
    return jdbc.query("""
      SELECT encrypted_access_token,iv_nonce,key_version FROM broker_credentials
      WHERE user_id=? AND broker_name=? AND token_expires_at>now()
      """,rs->{
      if(!rs.next())return null;
      int rowVersion=rs.getInt("key_version");
      VaultCrypto crypto=rowVersion==version?current:
        rowVersion==version-1?previous:null;
      if(crypto==null)throw new IllegalStateException("No key configured for credential version");
      return crypto.decrypt(user,broker,new VaultCrypto.Sealed(
        rs.getBytes("encrypted_access_token"),rs.getBytes("iv_nonce")));
    },user,broker);
  }
}
