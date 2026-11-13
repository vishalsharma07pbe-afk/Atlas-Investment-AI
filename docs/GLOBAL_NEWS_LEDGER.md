# Global news evidence ledger

## Purpose
A durable research ledger for manually submitted global and Indian news. It does **not** scrape websites, connect to a newswire, verify headlines, generate sentiment labels, predict market impacts or execute orders. The existing stateless news-analysis endpoint remains available.

## Workflow
1. Start the local application with `docker compose up --build -d`.
2. Open the Intraday, Swing or Short-Term workspace and locate **Global news evidence ledger**.
3. Enter a headline, publisher, HTTPS source URL and publication timestamp. The record is tagged as GLOBAL / OTHER / UNKNOWN by default; choose the desired region from the selector.
4. Save and review the stored list, publication time and freshness. The ledger uses a 72-hour freshness window; older evidence remains visible as stale. The URL is a user-provided reference and is never fetched by the backend.
5. Restart Docker containers to confirm persistence in the dedicated `newsledger` volume.

## API
- `POST /api/v1/intelligence/news/ledger` with existing `NewsRequest` schema, up to 100 events.
- `GET /api/v1/intelligence/news/ledger?limit=50&max_age_hours=72&geography=GLOBAL`

Entries are keyed by source URL and publication timestamp. Exact duplicate submissions are idempotent; conflicting entries return HTTP 409 without changing existing evidence. URLs must use HTTPS and cannot contain credentials or localhost/internal hostnames. This validation is **not** an independent source-verification guarantee.

## Verification
Run `cd intelligence && python3 -m unittest discover -s tests -p 'test_news_ledger.py'`. CI also runs the existing Python tests, React build/tests, Compose config and Spring Boot checks. Merge only after all checks pass.

## Access and licensing
No automatic collection is enabled. Any future newswire or API adapter must be implemented behind a separate provider entitlement, licensing, rate-limit and freshness gate, with documented permitted usage. ATLAS remains local-only without user authentication; never expose its HTTP ports publicly. No real-time news claims or inferred sentiment scores are made.
