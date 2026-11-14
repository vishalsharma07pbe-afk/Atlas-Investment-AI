package com.trading.api;

import static org.assertj.core.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.ResultSetExtractor;
import java.sql.ResultSet;

class VersionedVaultReaderTest {
  @Test void currentAndPreviousKeysDecryptByVersionAndUnknownVersionFails() throws Exception {
    String current=key(),previous=key();
    UUID user=UUID.randomUUID();
    JdbcTemplate jdbc=Mockito.mock(JdbcTemplate.class);
    VersionedVaultReader reader=new VersionedVaultReader(jdbc,current,previous,2);
    var old=new VaultCrypto(previous).encrypt(user,"UPSTOX","old-token");
    var next=new VaultCrypto(current).encrypt(user,"UPSTOX","new-token");
    for(var test:List.of(new Case(1,old,"old-token"),new Case(2,next,"new-token"))){
      ResultSet rs=Mockito.mock(ResultSet.class);
      Mockito.when(rs.next()).thenReturn(true);
      Mockito.when(rs.getInt("key_version")).thenReturn(test.version);
      Mockito.when(rs.getBytes("encrypted_access_token")).thenReturn(test.sealed.ciphertext());
      Mockito.when(rs.getBytes("iv_nonce")).thenReturn(test.sealed.nonce());
      Mockito.when(jdbc.query(Mockito.anyString(),Mockito.<ResultSetExtractor<String>>any(),Mockito.eq(user),Mockito.eq("UPSTOX")))
        .thenAnswer(inv->((ResultSetExtractor<String>)inv.getArgument(1)).extractData(rs));
      assertThat(reader.decrypt(user,"UPSTOX")).isEqualTo(test.plain);
    }
    ResultSet rs=Mockito.mock(ResultSet.class);
    Mockito.when(rs.next()).thenReturn(true);
    Mockito.when(rs.getInt("key_version")).thenReturn(0);
    Mockito.when(jdbc.query(Mockito.anyString(),Mockito.<ResultSetExtractor<String>>any(),Mockito.eq(user),Mockito.eq("UPSTOX")))
      .thenAnswer(inv->((ResultSetExtractor<String>)inv.getArgument(1)).extractData(rs));
    assertThatThrownBy(()->reader.decrypt(user,"UPSTOX")).isInstanceOf(IllegalStateException.class);
  }
  record Case(int version,VaultCrypto.Sealed sealed,String plain){}
  static String key(){byte[] bytes=new byte[32];new java.security.SecureRandom().nextBytes(bytes);return Base64.getEncoder().encodeToString(bytes);}
}
