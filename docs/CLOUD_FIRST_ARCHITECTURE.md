# Cloud-first execution boundaries

ATLAS is a research alpha, not a finished cloud service. The local Docker stack is for development; it is **not** an authenticated public deployment.

## Resource budget

- **Laptop:** browser and VS Code; no requirement to run the five-container stack continuously.
- **Backend:** deploy Spring Boot and FastAPI independently. FastAPI now reads `ATLAS_BACKEND_URL` for both market research and portfolio research instead of assuming the Docker-only hostname.
- **Database:** provision PostgreSQL with restricted network access, backups, and a migration plan. Do not migrate personal holdings without explicit consent.
- **Jobs:** use short-lived scheduled tasks for permitted data ingestion and feature computation, not an always-running local scraper or model.
- **Cache:** Redis is optional until a measured use case justifies it.
- **AI:** start with deterministic indicators and batch research; avoid persistent local inference.

## Required before any public or remote deployment

1. Implement authentication and authorization on Spring and FastAPI endpoints.
2. Require TLS, scoped secrets, rate limits, network restrictions, and audit logs.
3. Secure the PostgreSQL database, encrypt backups, and test restoration.
4. Verify exchange/provider licenses and freshness before enabling collection.
5. Establish service-to-service authentication; `ATLAS_BACKEND_URL` is configuration, **not** an authentication or SSRF defense.
6. Add end-to-end CI integration tests and operational monitoring.

Do not expose current API endpoints publicly or copy a local `.env` into GitHub.

## Configuration

`ATLAS_BACKEND_URL` should point to the **trusted, internal** Spring API origin (no trailing path), e.g. `http://backend:8080` in Compose. Only operators should control this environment variable. For cloud deployment use a private internal service URL, not a user-supplied URL.

The portfolio client enforces a fixed path, five-second timeout and a two-megabyte response cap. Cloud routing support does **not** make the portfolio API secure for internet access.
