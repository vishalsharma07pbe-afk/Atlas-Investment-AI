"""Permission-gated, local-directory feed adapter for recurring IPO alert snapshots.

This deliberately has no HTTP client or scheduler: sources must be supplied through
a separately authorized channel. Operator can run the sync on a chosen schedule.
"""
import argparse,hashlib,json,os
from pathlib import Path
from pydantic import BaseModel,Field,model_validator
from .notification_import import Snapshot,import_snapshot

class FeedConfig(BaseModel):
    source_name:str=Field(min_length=2,max_length=100)
    source_url:str=Field(pattern=r"^https://[^\\s]+$",max_length=1000)
    collection_authorized:bool=False
    redistribution_authorized:bool=False
    enabled:bool=False
    @model_validator(mode="after")
    def check_permissions(self):
        if self.enabled and not (self.collection_authorized and self.redistribution_authorized):
            raise ValueError("Enabled feed must have explicit collection and redistribution rights")
        return self

class Registry(BaseModel):
    feeds:list[FeedConfig]=Field(max_length=30)
    @model_validator(mode="after")
    def unique(self):
        if len({f.source_name for f in self.feeds})!=len(self.feeds):
            raise ValueError("Duplicate source names")
        return self

def sync_directory(registry_path:Path,inbox:Path,output:Path,apply:bool=False)->dict:
    if registry_path.stat().st_size>128*1024:raise ValueError("Registry exceeds 128KB")
    registry=Registry.model_validate_json(registry_path.read_bytes())
    if not inbox.is_dir():raise ValueError("Inbox must be a directory")
    results=[]
    # Never follow symlinks to files outside the operator-controlled inbox.
    files=sorted(p for p in inbox.iterdir() if p.suffix==".json" and p.is_file() and not p.is_symlink())
    if len(files)>100:raise ValueError("Too many inbox files")
    for path in files:
        if path.stat().st_size>1024*1024:
            results.append({"file":path.name,"status":"REJECTED","reason":"SIZE_LIMIT"});continue
        try:
            snap=Snapshot.model_validate_json(path.read_bytes())
            source=next((f for f in registry.feeds if f.source_name==snap.source_name),None)
            if source is None or not source.enabled:
                results.append({"file":path.name,"status":"SKIPPED","reason":"SOURCE_NOT_ENABLED"});continue
            if source.source_url!=snap.source_url or not(source.collection_authorized and source.redistribution_authorized):
                results.append({"file":path.name,"status":"REJECTED","reason":"SOURCE_MISMATCH_OR_RIGHTS"});continue
            outcome=import_snapshot(path,output,dry_run=not apply)
            results.append({"file":path.name,**outcome})
        except (ValueError,OSError,TypeError) as exc:
            results.append({"file":path.name,"status":"REJECTED","reason":type(exc).__name__})
    return {"mode":"APPLY" if apply else "DRY_RUN","scanned":len(files),
        "results":results,"live_http_feed_connected":False,
        "notice":"Operator-supplied snapshots only; permissions are declarations, not verified legal rights."}

def main():
    parser=argparse.ArgumentParser(description="Review or sync permissioned local alert snapshots")
    parser.add_argument("--registry",type=Path,required=True)
    parser.add_argument("--inbox",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("../data/notifications/alerts.json"))
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    print(json.dumps(sync_directory(args.registry,args.inbox,args.output,apply=args.apply),indent=2))

if __name__=="__main__":main()
