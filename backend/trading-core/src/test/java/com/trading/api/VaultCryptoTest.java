package com.trading.api;
import static org.assertj.core.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class VaultCryptoTest {
  static String key(){byte[] bytes=new byte[32];new java.security.SecureRandom().nextBytes(bytes);return Base64.getEncoder().encodeToString(bytes);}
  @Test void roundTripTamperingAndIdentityBinding(){
    var crypto=new VaultCrypto(key());UUID user=UUID.randomUUID();
    var sealed=crypto.encrypt(user,"UPSTOX","upstox-private-test-token");
    assertThat(new String(sealed.ciphertext())).doesNotContain("upstox-private-test-token");
    assertThat(crypto.decrypt(user,"UPSTOX",sealed)).isEqualTo("upstox-private-test-token");
    byte[] corrupt=sealed.ciphertext().clone();corrupt[0]^=1;
    assertThatThrownBy(()->crypto.decrypt(user,"UPSTOX",new VaultCrypto.Sealed(corrupt,sealed.nonce())))
      .isInstanceOf(IllegalStateException.class);
    assertThatThrownBy(()->crypto.decrypt(UUID.randomUUID(),"UPSTOX",sealed))
      .isInstanceOf(IllegalStateException.class);
  }
  @Test void rotationReencryptsWithNewKey(){
    var old=new VaultCrypto(key());var next=new VaultCrypto(key());UUID user=UUID.randomUUID();
    var sealed=old.encrypt(user,"UPSTOX","secret");
    var rotated=old.rotate(user,"UPSTOX",sealed,next);
    assertThat(next.decrypt(user,"UPSTOX",rotated)).isEqualTo("secret");
    assertThatThrownBy(()->old.decrypt(user,"UPSTOX",rotated)).isInstanceOf(IllegalStateException.class);
  }
}
