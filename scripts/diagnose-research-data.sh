#!/usr/bin/env bash
# Read-only diagnostic output. Never print env secrets, private holdings, provider payloads or tokens.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "=== Shared stock and fund ingestion (PostgreSQL) ==="
docker compose exec -T postgres sh -c 'psql -X -v ON_ERROR_STOP=1 -P pager=off -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
BEGIN READ ONLY;
SELECT e.code AS exchange,count(DISTINCT i.id) AS instruments,
       count(DISTINCT c.instrument_id) AS instruments_with_history,
       count(c.instrument_id) AS daily_candles,
       max((c.candle_time AT TIME ZONE 'Asia/Kolkata')::date) AS latest
FROM exchanges e LEFT JOIN instruments i ON i.exchange_id=e.id
LEFT JOIN market_candles c ON c.instrument_id=i.id AND c.timeframe='1d' AND c.is_complete
WHERE e.code IN ('NSE','BSE') GROUP BY e.code ORDER BY e.code;
SELECT e.code AS exchange,count(*) AS calendar_rows,
       max(s.session_date) FILTER(WHERE s.is_trading_day AND s.session_type='REGULAR' AND s.session_date<(now() AT TIME ZONE 'Asia/Kolkata')::date) AS latest_regular
FROM market_sessions s JOIN exchanges e ON e.id=s.exchange_id
WHERE e.code IN ('NSE','BSE') GROUP BY e.code ORDER BY e.code;
SELECT e.code AS exchange,a.status,count(*) AS attempts,max(a.attempted_at) AS last_attempt,sum(a.rows_written) AS written,min(a.next_attempt_at) AS next_attempt
FROM discovery_history_attempts a JOIN instruments i ON i.id=a.instrument_id JOIN exchanges e ON e.id=i.exchange_id
GROUP BY e.code,a.status ORDER BY e.code,a.status;
SELECT failure_code,failure_count,blocked_until,blocked_until>now() AS blocked FROM operator_feed_cooldown;
SELECT source_code,count(DISTINCT scheme_code) AS schemes,max(nav_date) AS latest FROM mutual_fund_nav GROUP BY source_code ORDER BY source_code;
COMMIT;
SQL
echo "=== Public research snapshots and jobs (Intelligence) ==="
docker compose exec -T intelligence python - <<'PY'
import os,sqlite3,json
from datetime import datetime,timezone
from pathlib import Path
flags=("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","MARKET_DATA_ENTITLEMENT_CONFIRMED","ATLAS_AUTONOMOUS_RESEARCH_ENABLED","ATLAS_GLOBAL_FX_ENABLED","ATLAS_GLOBAL_YIELDS_ENABLED","ATLAS_GLOBAL_OIL_ENABLED","ATLAS_ECONOMIC_CALENDAR_ENABLED")
for key in flags:
    print(key, "enabled" if os.getenv(key,"").lower()=="true" else "off")
for key in ("UPSTOX_ACCESS_TOKEN","FRED_API_KEY","TWELVE_DATA_API_KEY","EIA_API_KEY","ATLAS_GLOBAL_MARKETS_SERIES","ATLAS_GLOBAL_RELEASES_SOURCES"):
    print(key,"configured" if os.getenv(key,"").strip() else "not configured")
path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3"))
if not path.is_file():
    print("Research snapshot database not created yet.")
    raise SystemExit(0)
with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as db:
    db.row_factory=sqlite3.Row
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "research_sections" in tables:
        for row in db.execute("SELECT section,status,generated_at,error_code,payload FROM research_sections ORDER BY section"):
            try: result=json.loads(row["payload"] or "{}")
            except (ValueError,TypeError): result={}
            if not isinstance(result,dict):result={}
            if row["section"] in ("NSE","BSE"):
                details={k:result.get(k) for k in ("universe_size","eligible_count","skipped","discovery_coverage")}
            else:
                q=result.get("qualification_counts") or {}
                h=result.get("historical_coverage") or {}
                details={"history_count":len(h.get("items") or []),"growth_pick_count":len(result.get("growth_outlook") or []),"evaluated":q.get("evaluated_count"),"missing_gates":q.get("growth_missing_gate_counts")}
            print(row["section"],row["status"],row["generated_at"],row["error_code"],json.dumps(details,default=str))
    if "research_job_state" in tables:
        for row in db.execute("SELECT job,status,failures,error_code,next_due FROM research_job_state ORDER BY priority"):
            due=datetime.fromtimestamp(row["next_due"],timezone.utc).isoformat() if row["next_due"] else "pending"
            print(row["job"],row["status"],"failures",row["failures"],row["error_code"] or "-", "next",due)
PY
