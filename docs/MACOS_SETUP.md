# ATLAS on macOS (Apple Silicon)

ATLAS is a local research alpha. It does not execute trades or provide verified live recommendations.

## First run

1. Install Docker Desktop for Apple Silicon, and ensure Docker Desktop is running.
2. Open the repository folder in VS Code.
3. In its integrated terminal, run:

   ```bash
   cp .env.example .env
   ```

4. Open `.env`, set a **unique strong** `POSTGRES_PASSWORD`, and leave secrets out of Git.
5. Start the app:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

6. Open http://127.0.0.1:5173.

Stop services without deleting database data:

```bash
docker compose down
```

**Never use `docker compose down -v` unless you intentionally want to delete the database and Redis volumes.** Back up existing holdings before schema changes. Docker's init scripts only run when the PostgreSQL volume is first created.

## Updating from GitHub

```bash
git pull --ff-only
docker compose up --build -d
```

Check migration notes before rebuilding an installation with existing data. Keep the application bound to localhost: it has no authentication and stores personal holdings locally.

## Developer checks

- Frontend: `cd frontend/trading-dashboard && npm ci && npm test && npm run build`
- Intelligence: `cd intelligence && python3 -m pip install -r requirements.txt && python3 -m unittest discover -s tests -v`
- Backend compile: `cd backend/trading-core && mvn -DskipTests package`

GitHub Actions runs these checks for pull requests. Backend database integration tests require a properly initialized PostgreSQL database and are **not** currently run by that workflow. A green workflow is not proof that the full application is production ready.

## Market-data integrity

The dashboard must not display sample values as actual NSE/BSE prices. Validated imports, source licensing, freshness, and provenance are required before presenting market information as current.
