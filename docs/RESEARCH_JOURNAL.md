# Investment Research Journal

A local-first, user-authored research notebook for investment ideas. Complete module includes validated Python storage, CRUD API, React dashboard, tests and Docker persistence.

## Usage

Open **My Portfolio → Investment research journal**. Record a symbol, investment thesis, supporting evidence, risks, optional source reference and status (IDEA, RESEARCHING, MONITORING, CLOSED). Save, edit, delete or filter notes by status. The dashboard loads existing notes when opened.

Endpoints:
- `GET /api/v1/intelligence/journal` returns `{"entries":[...]}`, newest first.
- `POST /api/v1/intelligence/journal` accepts `{"symbol":"TEST","thesis":"My documented thesis","evidence":"Research notes","risks":"Downside factors","source_url":"","status":"IDEA"}` and returns the created record.
- `PUT /api/v1/intelligence/journal/{id}` replaces the editable fields.
- `DELETE /api/v1/intelligence/journal/{id}` deletes a note.

The intelligence container mounts `./data/research-journal` at `/app/journal`, with `ATLAS_RESEARCH_JOURNAL_FILE=/app/journal/entries.json`. Data survives container recreation if the host directory is preserved. Keep backups and restrict access to your local machine. The service is intended for single-user local use; it has **no authentication** and should not be exposed on a public network.

Validation limits: 200 notes, 1 MiB file, bounded text fields, atomic file replacement, and no symlink file target. Writes use a process-local lock; multiple replicas or processes writing the same file are unsupported. Corrupt or oversized storage fails closed instead of silently discarding notes.

**Research notes are user-authored and unverified**. The module does not fetch live market data, validate evidence, recommend investments or execute orders. Do not enter passwords, API tokens or sensitive credentials.
