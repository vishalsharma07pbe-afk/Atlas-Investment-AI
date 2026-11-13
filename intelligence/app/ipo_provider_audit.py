"""Bounded, secret-free local audit of explicit authorized IPO provider imports."""
import argparse,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from .authorized_ipo_provider import sync_provider

def _append_audit(path:Path,record:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError("Audit destination cannot be a symlink")
    # Keep a bounded JSON array and atomically replace it, rather than unbounded logs.
    existing=[]
    if path.exists():
        if path.stat().st_size>256*1024:raise ValueError("Audit history exceeds 256KB")
        existing=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing,list):raise ValueError("Invalid audit history")
    payload=json.dumps((existing+[record])[-100:],indent=2)+"\n"
    fd,name=tempfile.mkstemp(prefix=".provider-audit-",suffix=".json",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as file:
            file.write(payload);file.flush();os.fsync(file.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def run_audited_import(config_path:Path,output:Path,audit_path:Path,apply:bool=False)->dict:
    if output.resolve()==audit_path.resolve():
        raise ValueError("Audit file and alerts file must differ")
    record={"attempted_at":datetime.now(timezone.utc).isoformat(),
        "mode":"APPLY" if apply else "DRY_RUN",
        "outcome":"FAILED","error_category":None,
        "added":None,"updated":None,"skipped_older_or_equal":None,
        "retained":None,"input_sha256":None}
    try:
        result=sync_provider(config_path,output,apply=apply)
        record.update(outcome="SUCCESS",added=result["added"],updated=result["updated"],
            skipped_older_or_equal=result["skipped_older_or_equal"],
            retained=result["retained"],input_sha256=result["input_sha256"])
    except (ValueError,OSError,RuntimeError) as exc:
        # Never log exception messages, endpoints, Authorization headers or credentials.
        record["error_category"]=type(exc).__name__
    _append_audit(audit_path,record)
    return record

def main():
    parser=argparse.ArgumentParser(description="Audited, explicit IPO provider import")
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("../data/notifications/alerts.json"))
    parser.add_argument("--audit",type=Path,default=Path("../data/notifications/provider-import-audit.json"))
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    result=run_audited_import(args.config,args.output,args.audit,apply=args.apply)
    print(json.dumps(result,indent=2))
    if result["outcome"]!="SUCCESS":raise SystemExit(1)

if __name__=="__main__":main()
