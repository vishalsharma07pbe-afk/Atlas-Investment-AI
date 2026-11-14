# Dual-key vault cutover (operator procedure)

1. Back up the database and stop or quiesce broker-token writes. Generate a fresh 32-byte AES key; never paste either key in logs or arguments.
2. Set `ATLAS_VAULT_PREVIOUS_KEY` to the old base64 key, `ATLAS_VAULT_MASTER_KEY` to the new base64 key, and increment `ATLAS_VAULT_KEY_VERSION` by exactly one. During cutover, `VersionedVaultReader` uses the current key for current-version rows and previous key for previous-version rows. Unknown versions fail closed.
3. Run the dedicated process with environment variables set, using `--spring.profiles.active=vault-rotate --spring.main.web-application-type=none`. No key material belongs in command-line flags. The runner reports only the number of rotated rows. A DB transaction protects all selected rows.
4. Confirm all credential rows now have the new key version, restart normal backend instances with the new master key, and remove `ATLAS_VAULT_PREVIOUS_KEY` only after verification.

**Important:** This is a staged cutover, not a guarantee of uninterrupted availability. Token writes must be quiesced or coordinated; otherwise old-key writers can overwrite rows during the transition. Do not claim zero downtime without validating deployment orchestration and multi-instance behavior. The AI proxy stays disabled until real cross-service security tests pass.
