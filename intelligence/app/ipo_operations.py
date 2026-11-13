"""Read-only, bounded operational history of local IPO provider imports."""
import json,os
from pathlib import Path

def import_history(path:Path|None=None)->dict:
    target=path or Path(os.getenv("ATLAS_IPO_IMPORT_AUDIT","/app/data/provider-import-audit.json"))
    if not target.is_file():
        return {"status":"NOT_CONFIGURED","attempts":[],"total":0,
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
    return {"status":"LOCAL_AUDIT_HISTORY","attempts":attempts,"total":len(attempts),
            "notice":"Local operator records only; not evidence of a live feed or licensed exchange data."}
