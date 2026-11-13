"""Offline, permission-gated import of operator-supplied IPO and market alert snapshots.

Never downloads, scrapes, or manufactures live data.
"""
import argparse,hashlib,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from pydantic import BaseModel,Field,model_validator
from .notifications import Alert

class Snapshot(BaseModel):
    source_name:str=Field(min_length=2,max_length=100)
    source_url:str=Field(pattern=r"^https://[^\\s]+$",max_length=1000)
    retrieved_at:datetime
    collection_authorized:bool
    redistribution_authorized:bool
    alerts:list[Alert]=Field(max_length=200)

    @model_validator(mode="after")
    def validate_snapshot(self):
        if not (self.collection_authorized and self.redistribution_authorized):
            raise ValueError("Explicit source collection and redistribution permissions required")
        if self.retrieved_at.tzinfo is None or self.retrieved_at>datetime.now(timezone.utc):
            raise ValueError("Retrieved timestamp must be timezone-aware and not future-dated")
        if any(a.source_name!=self.source_name or a.source_url!=self.source_url for a in self.alerts):
            raise ValueError("Alert source attribution must match snapshot")
        if any(a.published_at>self.retrieved_at for a in self.alerts):
            raise ValueError("Alert publication must predate snapshot retrieval")
        if len({a.id for a in self.alerts})!=len(self.alerts):
            raise ValueError("Duplicate IDs in snapshot")
        return self

def import_snapshot(input_path:Path,output_path:Path,dry_run:bool=True)->dict:
    if input_path.resolve()==output_path.resolve():raise ValueError("Input and output must differ")
    if input_path.stat().st_size>1024*1024:raise ValueError("Snapshot exceeds 1MB")
    data=input_path.read_bytes()
    snapshot=Snapshot.model_validate_json(data)
    existing=[]
    if output_path.exists():
        if output_path.stat().st_size>1024*1024:raise ValueError("Existing feed exceeds 1MB")
        raw=json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(raw,list) or len(raw)>200:raise ValueError("Invalid existing feed")
        existing=[Alert.model_validate(x) for x in raw]
        if len({a.id for a in existing})!=len(existing):raise ValueError("Duplicate existing IDs")
    combined={a.id:a for a in existing}
    added=updated=skipped=0
    for alert in snapshot.alerts:
        old=combined.get(alert.id)
        if old is not None and alert.published_at<=old.published_at:
            skipped+=1
            continue
        if old is None:added+=1
        else:updated+=1
        combined[alert.id]=alert
    records=sorted(combined.values(),key=lambda a:(a.published_at,a.id),reverse=True)[:200]
    payload=json.dumps([a.model_dump(mode="json") for a in records],indent=2,ensure_ascii=False)+"\n"
    if len(payload.encode("utf-8"))>1024*1024:raise ValueError("Output exceeds 1MB")
    if not dry_run:
        output_path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=".alerts-",suffix=".json",dir=output_path.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name,output_path)
        finally:
            if os.path.exists(name):os.unlink(name)
    return {"status":"DRY_RUN" if dry_run else "IMPORTED","source":snapshot.source_name,
        "input_sha256":hashlib.sha256(data).hexdigest(),"added":added,"updated":updated,
        "skipped_older_or_equal":skipped,"retained":len(records),
        "note":"Operator-supplied and permission-declared; no independent source authenticity verification."}

def main():
    parser=argparse.ArgumentParser(description="Import permissioned local IPO/market alert snapshots")
    parser.add_argument("snapshot",type=Path)
    parser.add_argument("--output",type=Path,default=Path("data/notifications/alerts.json"))
    parser.add_argument("--apply",action="store_true",help="Actually update feed; otherwise dry run")
    args=parser.parse_args()
    print(json.dumps(import_snapshot(args.snapshot,args.output,dry_run=not args.apply),indent=2))

if __name__=="__main__":main()
