# Backup and disaster recovery

## Backup policy

The production backup command creates a PostgreSQL custom-format dump and a quiesced archive of NAV, OHLCV, ingestion, flow, news, reliability, and research-journal state. The intelligence service is briefly stopped so SQLite files are consistent; PostgreSQL remains online.

Run `ATLAS_PRODUCTION_ENV_FILE=/secure/path/atlas.env ATLAS_BACKUP_DIR=/secure/staging scripts/backup-production.sh`, then verify the new directory with `python3 scripts/verify-production-backup.py /secure/staging/<timestamp>`.

The verifier checks SHA-256 integrity and archive path safety. It does not prove restorability. Encrypt the verified directory, copy it to a separate account/region or offline medium, and apply a documented retention policy. Treat it as private financial data.

## Restore drill

Perform quarterly in an isolated environment with no provider credentials and no public network route:

1. Verify checksums and decrypt only into a restricted temporary directory.
2. Start a new empty PostgreSQL instance at the same or a compatible major version.
3. Inspect with `pg_restore --list postgres.dump`; restore into the empty database without `--clean` against any existing environment.
4. Validate row counts, Flyway state, user isolation, holdings totals, instrument counts, candle coverage, and quality-event counts.
5. Inspect the intelligence archive for expected root directories, then restore it only into new empty volumes.
6. Start the pinned application release with external providers disabled.
7. Run login, portfolio, research, data-health, and P3 smoke tests.
8. Destroy the isolated drill environment and securely erase decrypted temporary files.
9. Record recovery-point age, recovery time, failures, fixes, operator, and approval.

Never test restoration by overwriting the live database. Never use `docker compose down -v` as an operational shortcut.

