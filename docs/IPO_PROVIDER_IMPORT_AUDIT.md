# Audited IPO provider import

For an operator-visible, bounded local history of explicit authorized IPO feed import attempts, run:

```bash
cd intelligence
python3 -m app.ipo_provider_audit --config provider.json
python3 -m app.ipo_provider_audit --config provider.json --apply
```

Dry-run is the default; `--apply` updates the existing local alerts file only after the existing HTTPS and schema checks. Each attempt appends a record to `../data/notifications/provider-import-audit.json` using an atomic file replacement, retaining the most recent **100** attempts. An optional `--audit` path can be supplied.

Each record includes UTC attempt time, dry-run/apply mode, success/failure, input SHA-256 and imported/updated/skipped counts when available. Failure records include only a coarse exception class, never the exception message, endpoint, raw payload or bearer token. The CLI exits nonzero on an import failure.

The audit is a **local operational record**, not proof of exchange provenance, licensing or live streaming. The caller must protect the audit directory and must configure a real rights-cleared provider before using the adapter. Audit-write failures propagate; they do not imply that an already completed alert import was rolled back. See [AUTHORIZED_IPO_PROVIDER.md](AUTHORIZED_IPO_PROVIDER.md).
