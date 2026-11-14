package com.trading.api;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** Operator-only, env-only rotation. No key material accepted via CLI args. */
@Component
@Profile("vault-rotate")
public class VaultRotationRunner implements ApplicationRunner {
  private final VaultRotationService service;
  public VaultRotationRunner(VaultRotationService service){this.service=service;}
  @Override public void run(ApplicationArguments args){
    if(!args.getNonOptionArgs().isEmpty() ||
       args.getOptionNames().stream().anyMatch(s->s.toLowerCase().contains("key")))
      throw new IllegalArgumentException("Vault key arguments are forbidden");
    String old=System.getenv("ATLAS_VAULT_PREVIOUS_KEY");
    String next=System.getenv("ATLAS_VAULT_MASTER_KEY");
    String version=System.getenv("ATLAS_VAULT_KEY_VERSION");
    if(old==null || next==null || version==null || old.isBlank() || next.isBlank())
      throw new IllegalStateException("Missing rotation environment variables");
    int target=Integer.parseInt(version);
    if(target<2)throw new IllegalArgumentException("Rotation requires key version >=2");
    int count=service.rotateVersioned(old,next,target-1,target);
    System.out.println("Vault rotation completed; rows="+count);
    // This dedicated process exits after the transaction. Never expose an HTTP listener.
    System.exit(0);
  }
}
