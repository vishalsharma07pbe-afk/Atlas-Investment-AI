# ATLAS production topology

## Trust boundaries

```text
Browser
  |
  | HTTPS (TLS terminates at an operator-managed edge proxy)
  v
ATLAS frontend :8080 (only published container port; loopback by default)
  |-- /api/* ----------> Spring backend :8080
  `-- /intelligence/* -> FastAPI intelligence :8000
                              |
Spring backend -------------->| internal service token
  |
  `--------------------------> PostgreSQL/TimescaleDB :5432

FastAPI state -> six named application volumes
PostgreSQL    -> pgdata named volume
```

The `app` and `data` networks are Docker-internal. PostgreSQL, the Spring API,
and the intelligence API have no host-published ports. The frontend binds to
`127.0.0.1` so a production operator must deliberately place a TLS reverse
proxy or load balancer in front of it.

## Components and ownership

| Component | Responsibility | Persistent state |
|---|---|---|
| Frontend/Nginx | Static React bundle, same-origin routing, response security headers | None |
| Spring backend | Authentication, portfolio state, registry, API boundary | PostgreSQL/TimescaleDB |
| FastAPI intelligence | Validated research and provider adapters | Dedicated SQLite/JSON named volumes |
| PostgreSQL/TimescaleDB | Relational source of record and migrations | `pgdata` |
| Release workflow | Test, build, attest and publish immutable images | GHCR artifacts |

## Security properties

- Release images run as non-root users and their root filesystems are read-only.
- Secrets are injected at runtime and are never copied into image contexts.
- Registration is disabled in the production Compose contract.
- Only the frontend is reachable from the host; data and service networks are
  internal. Backend and intelligence receive egress only because optional,
  explicitly enabled providers may require it.
- Image tags are immutable SemVer-like release identifiers. Production must not
  use `latest`.
- The Content Security Policy permits only same-origin application traffic.

## Availability and recovery

The Compose topology is a single-host deployment foundation, not a highly
available cluster. Health checks and restart policies recover individual
processes, but host or volume loss requires restoration from an encrypted,
off-host backup. See [DISASTER_RECOVERY_RUNBOOK.md](../DISASTER_RECOVERY_RUNBOOK.md).

For multi-host availability, operators must supply a managed PostgreSQL service,
replicated application runtime, external TLS/load balancing, centralized secret
management and a tested backup target. Those services are intentionally not
pretended to exist in this repository.
