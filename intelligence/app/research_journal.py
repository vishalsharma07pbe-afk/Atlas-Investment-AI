"""Local research journal. No market data, broker access or trading actions."""
import json
import os
import tempfile
import threading
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel,Field

_LOCK=threading.RLock()
_MAX_RECORDS=200
_MAX_BYTES=1048576

class JournalEntryInput(BaseModel):
    symbol:str=Field(min_length=1,max_length=40,pattern=r"^[A-Za-z0-9._&-]+$")
    thesis:str=Field(min_length=3,max_length=2000)
    evidence:str=Field(default="",max_length=3000)
    risks:str=Field(default="",max_length=2000)
    source_url:str=Field(default="",max_length=500)
    status:Literal["IDEA","RESEARCHING","MONITORING","CLOSED"]="IDEA"

class JournalEntry(JournalEntryInput):
    id:str
    created_at:datetime
    updated_at:datetime

def _path()->Path:
    return Path(os.environ.get("ATLAS_RESEARCH_JOURNAL_FILE","/app/journal/entries.json"))

def _read(path:Path)->list[dict]:
    if path.is_symlink():raise ValueError("Journal path cannot be a symlink")
    if not path.exists():return []
    if path.stat().st_size>_MAX_BYTES:raise ValueError("Journal exceeds size limit")
    raw=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw,list) or len(raw)>_MAX_RECORDS:raise ValueError("Invalid journal structure")
    return [JournalEntry.model_validate(item).model_dump(mode="json") for item in raw]

def _write(path:Path,items:list[dict])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():raise ValueError("Journal path cannot be a symlink")
    data=json.dumps(items,ensure_ascii=False,separators=(",",":"))
    if len(data.encode("utf-8"))>_MAX_BYTES:raise ValueError("Journal exceeds size limit")
    fd,tmp=tempfile.mkstemp(prefix=".journal-",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def list_entries()->list[dict]:
    with _LOCK:return list(reversed(_read(_path())))

def create_entry(entry:JournalEntryInput)->dict:
    with _LOCK:
        path=_path();items=_read(path)
        if len(items)>=_MAX_RECORDS:raise ValueError("Journal entry limit reached")
        now=datetime.now(timezone.utc)
        item=JournalEntry(**entry.model_dump(),id=str(uuid4()),created_at=now,updated_at=now).model_dump(mode="json")
        items.append(item);_write(path,items)
        return item

def update_entry(entry_id:str,entry:JournalEntryInput)->dict|None:
    with _LOCK:
        path=_path();items=_read(path)
        for i,item in enumerate(items):
            if item["id"]==entry_id:
                updated=JournalEntry(**entry.model_dump(),id=entry_id,created_at=item["created_at"],
                    updated_at=datetime.now(timezone.utc)).model_dump(mode="json")
                items[i]=updated;_write(path,items);return updated
        return None

def delete_entry(entry_id:str)->bool:
    with _LOCK:
        path=_path();items=_read(path)
        remaining=[item for item in items if item["id"]!=entry_id]
        if len(remaining)==len(items):return False
        _write(path,remaining);return True
