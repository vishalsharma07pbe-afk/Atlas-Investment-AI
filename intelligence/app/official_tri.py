"""Scheduled authorized direct NSE Indices gross TRI CSV ingestion.

No invented endpoint, session emulation, redirect following or price substitution.
Each configured publisher URL must be verified and authorized by the operator.
"""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import csv
import io
import json
import os
import re
import sqlite3
import stat
import httpx
from . import fund_local_evidence as local, nav_catalog

IST=ZoneInfo("Asia/Kolkata")
PATH=Path("/app/fund-evidence/tri-sources.json")
VERSION="NSE-TRI-CSV-1"
INTERVAL=21600
MAX_BYTES=2_000_000
NOTICE=("Scheduled download of configured authorized publisher CSVs. No discovered or guessed URL; "
        "explicit gross total-return column and exact index/date identity required. "
        "HTTP source provenance is not proof of historical benchmark mandates or investment qualification.")

def permitted():
    return os.getenv("ATLAS_MF_OFFICIAL_TRI_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def valid_url(value):
    if not isinstance(value,str) or len(value)>500:return False
    p=urlsplit(value)
    return (p.scheme=="https" and p.netloc in ("www.niftyindices.com","niftyindices.com")
        and not p.query and not p.fragment and bool(re.fullmatch(r"/[A-Za-z0-9_./-]+\.csv",p.path,re.I))
        and not any(x in (".","..","") for x in p.path.split("/")[1:]))

def manifest(path=PATH):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>16000:raise ValueError("MANIFEST_SIZE")
        raw=stream.read(16001)
        after=os.fstat(stream.fileno())
        if before.st_mtime_ns!=after.st_mtime_ns or len(raw)!=after.st_size:raise ValueError("MANIFEST_CHANGED")
    obj=json.loads(raw,object_pairs_hook=local.unique)
    if not isinstance(obj,dict) or obj.get("schema")!=VERSION or obj.get("authorization_attested") is not True:raise ValueError("MANIFEST_SCHEMA")
    rows=obj.get("sources")
    if not isinstance(rows,list) or len(rows)>len(local.INDEXES):raise ValueError("MANIFEST_LIMIT")
    out={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"benchmark","url"} or row["benchmark"] not in local.INDEXES or row["benchmark"] in out or not valid_url(row["url"]):raise ValueError("MANIFEST_SOURCE")
        out[row["benchmark"]]=row["url"]
    if len(set(out.values()))!=len(out):raise ValueError("DUPLICATE_URL")
    return out

def parse(raw,benchmark,today):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES or benchmark not in local.INDEXES:raise ValueError("CSV_SIZE")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig"),newline=""),strict=True)
    headers=reader.fieldnames
    if headers not in (["IndexName","Date","Total Returns Index"],["IndexName","Date","Total Returns Index","Net Total Return Index"]):
        raise ValueError("GROSS_TRI_SCHEMA")
    expected=benchmark.removesuffix(" TRI")
    if expected=="NIFTY MULTICAP 50:25:25":expected="NIFTY500 MULTICAP 50:25:25"
    values={}
    for row in reader:
        if None in row or any(v is None for v in row.values()) or row["IndexName"].strip().upper() not in (expected,expected+" TRI"):raise ValueError("INDEX_IDENTITY")
        text=row["Date"].strip()
        try:d=local.day(text)
        except ValueError:d=datetime.strptime(text,"%d-%b-%Y").date()
        val=row["Total Returns Index"].strip()
        if not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,8})?",val):raise ValueError("TRI_NUMBER")
        number=float(val)
        if d in values or not today-timedelta(days=2000)<=d<=today or not local.num(number,.000001,1e12):raise ValueError("TRI_ROW")
        values[d]=number
        if len(values)>2000:raise ValueError("TRI_LIMIT")
    if len(values)<157 or max(values)-min(values)<timedelta(days=1092) or today-max(values)>timedelta(days=7):raise ValueError("TRI_HISTORY")
    return [{"date":d.isoformat(),"tri":values[d]} for d in sorted(values)]

def fetch(url):
    if not valid_url(url):raise ValueError("URL")
    data=bytearray()
    with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as client:
        with client.stream("GET",url,headers={"Accept":"text/csv,application/octet-stream","User-Agent":"ATLAS-Research/2.0"}) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data)>MAX_BYTES:raise ValueError("CSV_SIZE")
    return bytes(data)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS official_tri_downloads(
      benchmark TEXT PRIMARY KEY,url TEXT NOT NULL,attempted_at TEXT NOT NULL,
      status TEXT NOT NULL,source_hash TEXT,observations TEXT)""")

    # Keep last-good evidence separately from the last attempt. Failed refreshes
    # do not delete history, but archive rows are never admitted by read().
    db.execute("""CREATE TABLE IF NOT EXISTS official_tri_last_good(
      benchmark TEXT PRIMARY KEY,url TEXT NOT NULL,retrieved_at TEXT NOT NULL,
      source_hash TEXT NOT NULL,observations TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS official_tri_cooldown(
      singleton INTEGER PRIMARY KEY CHECK(singleton=1),blocked_until TEXT NOT NULL)""")
    db.execute("""INSERT OR IGNORE INTO official_tri_last_good
      SELECT benchmark,url,attempted_at,source_hash,observations
      FROM official_tri_downloads WHERE status='AVAILABLE' AND source_hash IS NOT NULL AND observations IS NOT NULL""")

def _retry_until(error,instant):
    # Shared publisher cooldown: rotating to another index must not evade 429.
    # Honor a valid numeric or HTTP-date Retry-After; retain a six-hour floor.
    deadline=instant+timedelta(seconds=INTERVAL)
    if not isinstance(error,httpx.HTTPStatusError) or error.response.status_code not in (429,503):
        return None
    value=error.response.headers.get("Retry-After","").strip()
    try:
        if re.fullmatch(r"[0-9]{1,12}",value):
            requested=instant+timedelta(seconds=int(value))
        else:
            requested=parsedate_to_datetime(value)
            if requested.tzinfo is None:requested=requested.replace(tzinfo=timezone.utc)
        deadline=max(deadline,requested)
    except (ValueError,TypeError,OverflowError):pass
    return deadline.astimezone(timezone.utc).isoformat()

def refresh(instant,*,path=PATH,loader=fetch,connect=None):
    if not permitted():return False
    connect=connect or nav_catalog._connect
    today=instant.astimezone(IST).date()
    try:links=manifest(path)
    except (OSError,ValueError,TypeError,KeyError):return False
    if not links:return False
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db)
        old={r["benchmark"]:r for r in db.execute("SELECT * FROM official_tri_downloads")}
        cooldown=db.execute("SELECT blocked_until FROM official_tri_cooldown WHERE singleton=1").fetchone()
        if cooldown and datetime.fromisoformat(cooldown["blocked_until"])>instant:
            return False
    due=[name for name in links if name not in old or old[name]["url"]!=links[name] or old[name]["attempted_at"]<=(instant-timedelta(seconds=INTERVAL)).isoformat()]
    if not due:return bool(read(instant,path=path,connect=connect)["indices"])
    # One publisher request per scheduler pass, round-robin by last attempt.
    name=min(due,key=lambda k:(old[k]["attempted_at"] if k in old else "",k))
    url=links[name];observations=None;digest=None;blocked_until=None
    try:
        raw=loader(url);observations=parse(raw,name,today);digest=sha256(raw).hexdigest()
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,httpx.HTTPError,csv.Error) as error:
        blocked_until=_retry_until(error,instant)
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO official_tri_downloads VALUES(?,?,?,?,?,?)
         ON CONFLICT(benchmark) DO UPDATE SET url=excluded.url,attempted_at=excluded.attempted_at,
          status=excluded.status,source_hash=excluded.source_hash,observations=excluded.observations
         WHERE excluded.attempted_at>=official_tri_downloads.attempted_at""",
         (name,url,instant.isoformat(),"AVAILABLE" if observations else "UNAVAILABLE",digest,json.dumps(observations,allow_nan=False) if observations else None))
        if observations:
            db.execute("""INSERT INTO official_tri_last_good VALUES(?,?,?,?,?)
              ON CONFLICT(benchmark) DO UPDATE SET url=excluded.url,retrieved_at=excluded.retrieved_at,
                source_hash=excluded.source_hash,observations=excluded.observations
              WHERE excluded.retrieved_at>=official_tri_last_good.retrieved_at""",
              (name,url,instant.isoformat(),digest,json.dumps(observations,allow_nan=False)))
        if blocked_until:
            db.execute("""INSERT INTO official_tri_cooldown VALUES(1,?)
              ON CONFLICT(singleton) DO UPDATE SET blocked_until=max(blocked_until,excluded.blocked_until)""",(blocked_until,))
    return observations is not None

def read(instant,*,path=PATH,connect=None):
    out={"status":"DISABLED_OR_NOT_AUTHORIZED","indices":{},"provenance":{},"configured_count":0,"last_good_count":0,"failed_count":0,"publisher_blocked_until":None,"notice":NOTICE}
    if not permitted():return out
    out["status"]="AWAITING_AUTHORIZED_SOURCE"
    connect=connect or nav_catalog._connect
    try:
        links=manifest(path);out["configured_count"]=len(links)
        if not links:return out
        out["status"]="AWAITING_CURRENT_TRI"
        with nav_catalog._LOCK,closing(connect()) as db,db:
            _table(db);rows=db.execute("SELECT * FROM official_tri_downloads WHERE status='AVAILABLE'").fetchall()
            archives=db.execute("SELECT benchmark,url FROM official_tri_last_good").fetchall()
            failures=db.execute("SELECT benchmark,url FROM official_tri_downloads WHERE status='UNAVAILABLE'").fetchall()
            cooldown=db.execute("SELECT blocked_until FROM official_tri_cooldown WHERE singleton=1").fetchone()
        out["last_good_count"]=sum(links.get(r["benchmark"])==r["url"] for r in archives)
        out["failed_count"]=sum(links.get(r["benchmark"])==r["url"] for r in failures)
        if cooldown and datetime.fromisoformat(cooldown["blocked_until"])>instant:
            out["publisher_blocked_until"]=cooldown["blocked_until"]
        today=instant.astimezone(IST).date()
        for row in rows:
            name=row["benchmark"]
            if links.get(name)!=row["url"]:continue
            stamp=datetime.fromisoformat(row["attempted_at"])
            if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=48) or not re.fullmatch(r"[a-f0-9]{64}",row["source_hash"] or ""):continue
            points=json.loads(row["observations"])
            # Revalidate every cached observation under the current date.
            data={"schema":local.VERSION,"authorization_attested":True,"indices":[{"benchmark":name,"source_url":local.TRI_SOURCE,"series_type":"GROSS_TOTAL_RETURN_INDEX","observations":points}],"schemes":[]}
            values=local.parse(json.dumps(data,allow_nan=False).encode(),today)["indices"][name]
            if today-max(values)>timedelta(days=7):continue
            out["indices"][name]=values
            out["provenance"][name]={"source_url":row["url"],"source_sha256":row["source_hash"],"retrieved_at":row["attempted_at"],"status":"AUTHORIZED_DIRECT_CSV"}
        if out["indices"]:out["status"]="CURRENT_TRI_AVAILABLE"
    except (OSError,ValueError,TypeError,KeyError,AttributeError,sqlite3.Error):
        out.update(status="UNAVAILABLE",indices={},provenance={})
    return out

def combine(loaded,downloaded):
    """Do not silently merge conflicting series or infer fund benchmark identity."""
    indices=dict(loaded.get("indices",{}));provenance={};conflicts=[]
    for name,series in downloaded.get("indices",{}).items():
        old=indices.get(name,{})
        if any(abs(old[d]-series[d])>max(.000001,abs(series[d])*1e-8) for d in old.keys() & series.keys()):
            indices.pop(name,None);conflicts.append(name);continue
        indices[name]=series
        provenance[name]=downloaded["provenance"][name]
    return {**loaded,"indices":indices,"downloaded_tri_provenance":provenance,"tri_conflicts":conflicts}
