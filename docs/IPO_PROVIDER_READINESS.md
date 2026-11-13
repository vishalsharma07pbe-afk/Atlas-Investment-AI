# Offline IPO provider readiness check

Before running the authorized HTTPS IPO adapter, inspect local configuration **without any DNS or HTTP requests**:

```bash
cd intelligence
python3 -m app.ipo_provider_readiness --config provider.json
```

Output includes `status`, `ready`, `network_requested:false`, `provider`, `endpoint_host`, and individual checks for configuration validity, enablement, declared collection and redistribution permissions, and bearer token environment-variable presence.

Possible statuses: `NOT_CONFIGURED`, `INVALID_CONFIG`, `BLOCKED`, `READY_FOR_CONNECTION_TEST`. A ready status **does not mean connected, authenticated, licensed, or that any market data is current**. It only means local prerequisites appear to be satisfied.

No bearer token value, full endpoint URL, HTTP request, or DNS lookup is included in this check. Configure the actual rights-cleared endpoint and token as described in [AUTHORIZED_IPO_PROVIDER.md](AUTHORIZED_IPO_PROVIDER.md). The adapter remains manually invoked, with dry-run as its default.
