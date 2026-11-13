"""Read-only, bounded operational history of local IPO provider imports."""
import json,os
from datetime import datetime,timezone
from pathlib import Path

def import_history(path:Path|None=None)->dict:
    target=path or Path(os.getenv("ATLAS_IPO_IMPORT_AUDIT","/app/data/provider-import-audit.json"))
    if not target.is_file():
        return {"status":"NOT_CONFIGURED","attempts":[],"total":0,"freshness":_import_freshness([]),
                "notice":"No local provider import audit history is available."}
    if target.is_symlink() or target.stat().st_size>256*1024:
        raise ValueError("Invalid audit history destination or size")
    raw=json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw,list) or len(raw)>100:
        raise ValueError("Invalid audit history collection")
    attempts=[]
    for entry in reversed(raw):
        if not isinstance(entry,dict) or entry.get("outcome") not in ("SUCCESS","FAILED") or entry.get("mode") not in ("APPLY","DRY_RUN"):
            raise ValueError("Invalid audit entry")
        # Explicit allowlist prevents accidental disclosure of stored provider secrets.
        attempts.append({key:entry.get(key) for key in (
            "attempted_at","mode","outcome","error_category","added","updated",
            "skipped_older_or_equal","retained","input_sha256")})
    freshness=_import_freshness(attempts)
    return {"status":"LOCAL_AUDIT_HISTORY","attempts":attempts,"total":len(attempts),"freshness":freshness,
            "notice":"Local operator records only; not evidence of a live feed or licensed exchange data."}

def _import_freshness(attempts:list[dict],now:datetime|None=None)->dict:
    """A successful APPLY is an import, not proof of source publication freshness."""
    now=now or datetime.now(timezone.utc)
    last_dry_run=None
    last_applied=None
    for item in attempts:
        if item.get("outcome")!="SUCCESS":continue
        stamp=item.get("attempted_at")
        if not isinstance(stamp,str):continue
        try:
            parsed=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if parsed.tzinfo is None:continue
            parsed=parsed.astimezone(timezone.utc)
        except ValueError:continue
        if parsed>now:continue
        if item["mode"]=="DRY_RUN" and (last_dry_run is None or parsed>last_dry_run):
            last_dry_run=parsed
        if item["mode"]=="APPLY" and (last_applied is None or parsed>last_applied):
            last_applied=parsed
    age_hours=round((now-last_applied).total_seconds()/3600,2) if last_applied else None
    status="NO_SUCCESSFUL_IMPORT" if last_applied is None else "IMPORT_STALE" if age_hours>24 else "RECENT_IMPORT"
    return {"status":status,"last_successful_apply_at":last_applied.isoformat() if last_applied else None,
        "last_successful_dry_run_at":last_dry_run.isoformat() if last_dry_run else None,
        "hours_since_successful_apply":age_hours,"stale_after_hours":24,
        "notice":"Measures local import activity only, not provider connectivity or market-data freshness."}
