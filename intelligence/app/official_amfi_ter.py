"""Opt-in AMFI website TER collector; exact operator-authenticated crosswalk.
The website JSON contract is independently documented, not a supported public API
or live verified entitlement. Fail closed on schema/access changes. Never join names.
"""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import json, os, re, sqlite3, stat, time
import httpx
from . import nav_catalog, fund_local_evidence as local

URL="https://www.amfiindia.com/api/populate-te-rdata-revised"
PATH=local.PATH.with_name("amfi-ter-crosswalk.json")
VERSION="AMFI-TER-WEBSITE-1"
IST=ZoneInfo("Asia/Kolkata")
INTERVAL=900
MAX_BYTES=8_000_000
PAGE_SIZE=10000
FIELDS=dict(base_expense_percent="D_BER",brokerage_percent="D_BrokerageCost",
    transaction_percent="D_TransactionCost",statutory_levies_percent="D_StatutoryLevies",ter_percent="D_TER")
NOTICE="AMFI website response with operator-authenticated NSDL-to-Direct-Growth crosswalk; not independently authenticated identity or qualified ranking evidence."

def permitted():
    return os.getenv("ATLAS_MF_AMFI_TER_AUTO_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def crosswalk(today,path=PATH):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        before=os.fstat(f.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=500000:raise ValueError("CROSSWALK_SIZE")
        raw=f.read(500001);after=os.fstat(f.fileno())
        if len(raw)!=before.st_size or before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError("CROSSWALK_CHANGED")
    data=json.loads(raw,object_pairs_hook=local.unique)
    rows=data["schemes"]
    if data.get("schema")!=VERSION or data.get("authorization_attested") is not True or not isinstance(rows,list) or not 1<=len(rows)<=1000:raise ValueError("CROSSWALK_SCHEMA")
    by={};codes=set();isins=set()
    for row in rows:
        amc=row["amc_id"];nsdl=row["nsdl_scheme_code"];code=row["scheme_code"];isin=row["isin_growth"]
        if (type(amc) is not int or not 1<=amc<=10000 or not isinstance(nsdl,str) or not re.fullmatch(r"[A-Za-z0-9/_.-]{1,120}",nsdl)
            or type(code) is not int or not 1<=code<=999999999 or not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin)
            or row.get("plan")!="DIRECT" or row.get("option")!="GROWTH"
            or not 0<=(today-local.day(row["verified_date"])).days<=90
            or (amc,nsdl) in by or code in codes or isin in isins):raise ValueError("CROSSWALK_IDENTITY")
        by[amc,nsdl]={"scheme_code":code,"isin_growth":isin,"plan":"DIRECT","option":"GROWTH"}
        codes.add(code);isins.add(isin)
    return by,sha256(raw).hexdigest()

def parse(raw,amc,month,today,mapping):
    if not 0<len(raw)<=MAX_BYTES:raise ValueError("RESPONSE_SIZE")
    obj=json.loads(raw,object_pairs_hook=local.unique,parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NONFINITE")))
    rows=obj["data"];meta=obj["meta"]
    if (not isinstance(rows,list) or not isinstance(meta,dict) or type(meta.get("total")) is not int
        or meta["total"]!=len(rows) or not 1<=len(rows)<=PAGE_SIZE or meta.get("page")!=1 or meta.get("pageCount")!=1):
        raise ValueError("RESPONSE_INCOMPLETE")
    out={};seen=set();digest=sha256(raw).hexdigest()
    for row in rows:
        if not isinstance(row,dict) or row.get("MF_ID") not in (amc,str(amc)) or row.get("Month")!=month:raise ValueError("RESPONSE_SCOPE")
        nsdl=row.get("NSDLSchemeCode")
        if not isinstance(nsdl,str):raise ValueError("RESPONSE_IDENTITY")
        key=(amc,nsdl)
        if key not in mapping:continue
        if row.get("SchemeType_Desc")!="Open Ended":raise ValueError("RESPONSE_SCHEME_TYPE")
        stamp=row["TER_Date"]
        if not isinstance(stamp,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.\d{1,6})?Z",stamp):raise ValueError("RESPONSE_DATE")
        day=local.day(stamp[:10])
        if day.strftime("%m-%Y")!=month or day>today:raise ValueError("RESPONSE_DATE")
        if (key,day) in seen:raise ValueError("DUPLICATE_RESPONSE_DATE")
        seen.add((key,day))
        vals={}
        for k,field in FIELDS.items():
            v=row[field]
            if not isinstance(v,str) or not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,6})?",v):raise ValueError("RESPONSE_COST")
            n=Decimal(v)
            if not 0<=n<=100:raise ValueError("RESPONSE_COST")
            vals[k]=n
        if abs(sum(vals[k] for k in FIELDS if k!="ter_percent")-vals["ter_percent"])>Decimal("0.0002"):raise ValueError("RESPONSE_COST_MISMATCH")
        code=str(mapping[key]["scheme_code"])
        if (today-day).days<=7 and (code not in out or out[code]["ter_date"]<day.isoformat()):
            out[code]={**mapping[key],"ter_date":day.isoformat(),**{k:float(v) for k,v in vals.items()},
                "source":"AMFI_WEBSITE_OPERATOR_CROSSWALK","source_sha256":digest}
    return out

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS official_amfi_ter_cache(
        scheme_code TEXT PRIMARY KEY,amc_id INTEGER NOT NULL,mapping_hash TEXT NOT NULL,
        collected_at TEXT NOT NULL,payload TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS official_amfi_ter_attempt(
        amc_id INTEGER PRIMARY KEY,attempted_at REAL NOT NULL,next_due REAL NOT NULL,status TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS official_amfi_ter_cooldown(
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),until REAL NOT NULL)""")

def _download(amc,month):
    deadline=time.monotonic()+30;raw=bytearray()
    with httpx.Client(timeout=12,follow_redirects=False,headers={"Accept":"application/json","User-Agent":"ATLAS-Research/1.0"}) as client:
        with client.stream("GET",URL,params={"MF_ID":amc,"Month":month,"strCat":"-1","strType":1,"page":1,"pageSize":PAGE_SIZE}) as response:
            response.raise_for_status()
            for part in response.iter_bytes():
                if time.monotonic()>deadline or len(raw)+len(part)>MAX_BYTES:raise ValueError("RESPONSE_LIMIT")
                raw.extend(part)
    return bytes(raw)

def refresh(instant=None,loader=_download,path=PATH):
    if not permitted():return 0
    instant=instant or datetime.now(timezone.utc);today=instant.astimezone(IST).date()
    try: mapping,digest=crosswalk(today,path)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return 0
    ts=instant.timestamp()
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _table(db);db.execute("BEGIN IMMEDIATE")
        block=db.execute("SELECT until FROM official_amfi_ter_cooldown WHERE singleton=1").fetchone()
        if block and block[0]>ts:return 0
        attempts={r["amc_id"]:r for r in db.execute("SELECT * FROM official_amfi_ter_attempt")}
        # A single AMC per scheduler pass; never retry before lease/cooldown.
        ids=sorted({k[0] for k in mapping},key=lambda a:(attempts[a]["attempted_at"] if a in attempts else 0,a))
        amc=next((a for a in ids if a not in attempts or attempts[a]["next_due"]<=ts),None)
        if amc is None:return 0
        db.execute("""INSERT INTO official_amfi_ter_attempt VALUES(?,?,?,'RUNNING')
          ON CONFLICT(amc_id) DO UPDATE SET attempted_at=excluded.attempted_at,next_due=excluded.next_due,status='RUNNING'""",(amc,ts,ts+1800))
        db.execute("""INSERT INTO official_amfi_ter_cooldown VALUES(1,?)
          ON CONFLICT(singleton) DO UPDATE SET until=MAX(until,excluded.until)""",(ts+INTERVAL,))
    try:
        month=today.strftime("%m-%Y");items=parse(loader(amc,month),amc,month,today,mapping)
        status="AVAILABLE" if items else "NO_CURRENT_MATCHES";delay=86400;block=0
    except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError,InvalidOperation,OverflowError) as error:
        items={};status="UNAVAILABLE";delay=21600;block=ts+delay
        if isinstance(error,httpx.HTTPStatusError):
            hint=error.response.headers.get("Retry-After","")
            try:
                dt=instant+timedelta(seconds=int(hint)) if re.fullmatch(r"[0-9]{1,12}",hint) else parsedate_to_datetime(hint)
                if dt.tzinfo is not None:block=max(block,dt.timestamp())
            except (TypeError,ValueError,OverflowError):pass
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _table(db)
        updated=db.execute("UPDATE official_amfi_ter_attempt SET status=?,next_due=? WHERE amc_id=? AND attempted_at=? AND status='RUNNING'",
            (status,ts+delay,amc,ts)).rowcount
        if updated:
            # New successful snapshot replaces this AMC; a failed attempt
            # does not redate or destroy the last successful evidence.
            if status!="UNAVAILABLE":
                db.execute("DELETE FROM official_amfi_ter_cache WHERE amc_id=?",(amc,))
                db.executemany("INSERT OR REPLACE INTO official_amfi_ter_cache VALUES(?,?,?,?,?)",
                    [(c,amc,digest,instant.isoformat(),json.dumps(v,allow_nan=False)) for c,v in items.items()])
            if block:
                db.execute("UPDATE official_amfi_ter_cooldown SET until=MAX(until,?) WHERE singleton=1",(block,))
    return len(items) if updated else 0

def read(today,path=PATH):
    out={"status":"DISABLED_OR_NOT_AUTHORIZED","items":{},"notice":NOTICE}
    if not permitted():return out
    out["status"]="AWAITING_CURRENT_MAPPED_RESPONSE"
    try:
        mapping,digest=crosswalk(today,path);identities={str(v["scheme_code"]):v for v in mapping.values()}
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            _table(db)
            for row in db.execute("SELECT * FROM official_amfi_ter_cache WHERE mapping_hash=?",(digest,)):
                code=row["scheme_code"];v=json.loads(row["payload"]);expected=identities.get(code)
                if (not expected or any(v.get(k)!=value for k,value in expected.items()) or not 0<=(today-local.day(v["ter_date"])).days<=7
                    or v.get("source")!="AMFI_WEBSITE_OPERATOR_CROSSWALK" or not re.fullmatch(r"[a-f0-9]{64}",v.get("source_sha256",""))
                    or not all(local.num(v.get(k),0,100) for k in FIELDS)
                    or abs(sum(v[k] for k in FIELDS if k!="ter_percent")-v["ter_percent"])>.0002):continue
                out["items"][code]=v
        if out["items"]:out["status"]="CURRENT_MAPPED_RESPONSES"
    except (OSError,ValueError,TypeError,KeyError,AttributeError,sqlite3.Error):out["items"]={};out["status"]="AWAITING_CURRENT_MAPPED_RESPONSE"
    return out
