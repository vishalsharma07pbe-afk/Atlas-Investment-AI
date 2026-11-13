# ATLAS local deployment verification (Mac)

ATLAS is a private local research alpha, **not** a live market feed or trading system. All published ports bind to loopback. No broker orders or portfolio uploads are performed by these checks.

## Before starting
1. Install Docker Desktop, start its engine, and ensure enough free disk space for database images and volumes.
2. Copy the sample configuration: `cp .env.example .env`. Set a strong, unique `POSTGRES_PASSWORD`. Keep `.env` out of version control.
3. Validate configuration without starting containers: `docker compose config --quiet`. This must complete successfully.
4. Back up any existing database before upgrades. **Never run `docker compose down -v` on a database you want to keep.**

## Start and verify
1. Run `docker compose up --build -d`.
2. Run `docker compose ps`. Confirm PostgreSQL and backend report healthy and all four app services are running.
3. Run `curl -fsS http://127.0.0.1:8000/health` and `curl -fsS http://127.0.0.1:8080/api/v1/health`. Both must return healthy responses.
4. Open `http://127.0.0.1:5173`. Check the dashboard and Stock Explorer load.
5. Run `docker compose logs --tail=100 backend intelligence frontend` if a service fails.
6. Stop without removing stored data: `docker compose down`.

## Run tests independently
- Python: `cd intelligence && python3 -m pip install -r requirements.txt && python3 -m unittest discover -s tests -v`.
- React: `cd frontend/trading-dashboard && npm ci && npm test && npm run build`.
- Backend: `cd backend/trading-core && mvn -B -ntp -DskipTests package`. This compiles but does **not** execute database integration tests.
- Deployment syntax: `POSTGRES_PASSWORD=ci-placeholder docker compose config --quiet`.

## Fail-closed integration checks
The Python contract suite tests the combined risk qualification → alert evaluation → backtest pipeline using synthetic local daily candles. It verifies valid data, mixed adjustment rejection, insufficient history and backend unavailability. It does not validate real exchange feeds, provider SLAs, live notifications, production security or model prediction quality.

## Resource and security notes
All research checks are on demand; no scheduler is enabled by these tests. The full Docker stack still consumes CPU, memory and disk while running. Use `docker compose down` when idle. Redis and PostgreSQL retain local Docker volumes. Do not expose the service ports outside localhost: this alpha has no user authentication or encryption at rest.
