package com.trading.api;

import java.sql.ResultSet;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** All-row rotation is atomic; operator must switch active key only after commit. */
@Service
public class VaultRotationService {
  private final JdbcTemplate jdbc;
  private final String currentKey;
  VaultRotationService(JdbcTemplate jdbc,@Value("${ATLAS_VAULT_MASTER_KEY:}") String currentKey){
    this.jdbc=jdbc;this.currentKey=currentKey;
  }
  @Transactional
  public int rotate(String oldKey,String newKey){
    return rotateVersioned(oldKey,newKey,1,2);
  }
  @Transactional
  public int rotateVersioned(String oldKey,String newKey,int oldVersion,int newVersion){
    if(oldVersion<=0 || newVersion<=oldVersion)throw new IllegalArgumentException("Invalid key versions");
    if(currentKey==null || !currentKey.equals(newKey))
      throw new IllegalStateException("New key must match configured active key");
    if(oldKey.equals(newKey))throw new IllegalArgumentException("New key must differ");
    VaultCrypto oldCrypto=new VaultCrypto(oldKey),newCrypto=new VaultCrypto(newKey);
    var rows=jdbc.query("SELECT id,user_id,broker_name,encrypted_access_token,iv_nonce FROM broker_credentials WHERE key_version=? FOR UPDATE",
      (ResultSet rs,int index)->new Row(rs.getLong("id"),rs.getObject("user_id",UUID.class),
        rs.getString("broker_name"),rs.getBytes("encrypted_access_token"),rs.getBytes("iv_nonce")),oldVersion);
    for(Row row:rows){
      var next=oldCrypto.rotate(row.user(),row.broker(),new VaultCrypto.Sealed(row.ciphertext(),row.nonce()),newCrypto);
      jdbc.update("UPDATE broker_credentials SET encrypted_access_token=?,iv_nonce=?,key_version=?,updated_at=now() WHERE id=? AND key_version=?",
        next.ciphertext(),next.nonce(),newVersion,row.id(),oldVersion);
    }
    return rows.size();
  }
  private record Row(long id,UUID user,String broker,byte[] ciphertext,byte[] nonce){}
}
