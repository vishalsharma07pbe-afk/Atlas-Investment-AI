package com.trading.api;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.UUID;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/** Isolated cryptographic primitive; never log or expose decrypted tokens. */
public final class VaultCrypto {
  private final SecretKeySpec key;
  private final SecureRandom random = new SecureRandom();
  public VaultCrypto(String base64Key) {
    byte[] raw=Base64.getDecoder().decode(base64Key);
    if(raw.length!=32)throw new IllegalArgumentException("AES-256 key must be 32 bytes");
    key=new SecretKeySpec(raw,"AES");
    Arrays.fill(raw,(byte)0);
  }
  public record Sealed(byte[] ciphertext,byte[] nonce){}
  public Sealed encrypt(UUID user,String broker,String token){
    byte[] nonce=new byte[12];random.nextBytes(nonce);
    try {
      Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.ENCRYPT_MODE,key,new GCMParameterSpec(128,nonce));
      cipher.updateAAD(aad(user,broker));
      return new Sealed(cipher.doFinal(token.getBytes(StandardCharsets.UTF_8)),nonce);
    }catch(Exception ex){throw new IllegalStateException("Encryption failed",ex);}
  }
  public String decrypt(UUID user,String broker,Sealed sealed){
    try {
      Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,sealed.nonce()));
      cipher.updateAAD(aad(user,broker));
      return new String(cipher.doFinal(sealed.ciphertext()),StandardCharsets.UTF_8);
    }catch(Exception ex){throw new IllegalStateException("Authentication/decryption failed");}
  }
  public Sealed rotate(UUID user,String broker,Sealed sealed,VaultCrypto nextKey){
    return nextKey.encrypt(user,broker,decrypt(user,broker,sealed));
  }
  private static byte[] aad(UUID user,String broker){
    return (user.toString()+":"+broker).getBytes(StandardCharsets.UTF_8);
  }
}
