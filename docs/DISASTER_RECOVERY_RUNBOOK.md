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


## Automated release recovery gate

The production integration workflow now invokes `scripts/ci_recovery_drill.py --disposable-ci-stack` after the real gateway contract test. It uses the actual production backup command with generated credentials and synthetic holdings; checks archive integrity; extracts SQLite state into temporary storage, runs integrity checks, verifies the exact immutable synthetic public market alert (identity, original recording timestamp and payload) and confirms its scheduler registration; restores the PostgreSQL dump into a uniquely named container on no network using the identical source image and TimescaleDB pre/post-restore procedures; compares selected table counts, migration state and saved holding ownership/values. Cleanup targets only that container and its anonymous volumes. The synthetic alert is generated through the existing market-risk producer and history writer only in the guarded disposable CI intelligence volume; no source PostgreSQL write or provider request is introduced. It refuses to run outside the named disposable CI project. This is not a live restore tool, full application recovery test, or proof of real-data RPO/RTO. The manual isolated production recovery drill remains required.

The production gateway job also checks 100 health requests at concurrency five (zero failures, p95 <= 750 ms). This is a bounded synthetic readiness check, not a representative portfolio-load or soak test.
