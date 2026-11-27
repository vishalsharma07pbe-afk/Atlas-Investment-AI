"""Official sector price-index comparisons, separate from local peer medians."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from math import isfinite
from zoneinfo import ZoneInfo
import json
import os

from .market_client import backend_json
from . import relative_strength,automatic_company_evidence
from .replay_evidence import exact_isin

IST=ZoneInfo("Asia/Kolkata")
INTERVAL=1800
KEYS=tuple("NSE_INDEX|Nifty "+name for name in ("Bank","IT","Auto","Pharma","FMCG","Metal"))
# Conservative explicit classification proxy, never fuzzy keyword guessing
# or broad financial services -> banks. Not an index membership assertion.
LABELS={
    "banks":KEYS[0],"banking":KEYS[0],"information technology":KEYS[1],
    "automobile":KEYS[2],"automobiles":KEYS[2],"pharmaceuticals":KEYS[3],
    "pharmaceutical":KEYS[3],"fast moving consumer goods":KEYS[4],"fmcg":KEYS[4],
    "metals":KEYS[5],"metal":KEYS[5]}
NOTICE=("Official named NSE price index via authorized Upstox history. Narrow current provider classification maps to a "
        "comparison proxy, not index membership. Exact stored NSE session dates and adjusted provider-validated stock observations. "
        "Not total return, point-in-time sector classification, independent adjustment proof, forecast or calibrated ranking. "
        "No BSE index substitution. Candidate provider keys require live acceptance.")

def permitted():
    return os.getenv("ATLAS_SECTOR_BENCHMARKS_ENABLED","false").lower()=="true" and automatic_company_evidence.permitted()

def mapping(labels):
    if not isinstance(labels,(list,tuple)) or len(labels)!=2:return None
    sector,industry=labels
    # Prefer precise industry when sector is broad only for banking and pharma.
    explicit=LABELS.get(industry)
    broad=LABELS.get(sector)
    if explicit and broad and explicit!=broad:return None
    if explicit in (KEYS[0],KEYS[3]):return explicit
    return broad

def analyze(data,calendar,today):
    items=data.get("items") if isinstance(data,dict) else None
    if not isinstance(items,list) or len(items)>len(KEYS):return {}
    by_key={}
    seen=set()
    for item in items:
        if not isinstance(item,dict):return {}
        key=item.get("benchmark_key")
        if key not in KEYS or key in seen:return {}
        seen.add(key)
        rows=item.get("candles")
        if item.get("kind")!="PRICE_INDEX" or not isinstance(rows,list) or not 21<=len(rows)<=400:continue
        indexed={}
        try:
            for row in rows:
                day=date.fromisoformat(row["trade_date"]);v=float(row["close"])
                if day>=today or day in indexed or row.get("source_code")!="UPSTOX" or type(row.get("revision")) is not int or row["revision"]<1 or not isfinite(v) or not 0<v<=1e9:
                    raise ValueError("INDEX_ROW")
                indexed[day]=v
            windows=relative_strength.benchmark_windows(indexed,calendar,today)
            if windows and 1<=(today-max(indexed)).days<=7:
                by_key[key]={"benchmark_key":key,"as_of":max(indexed).isoformat(),"calendar_checked_on":today.isoformat(),"windows":windows}
        except (ValueError,TypeError,KeyError,OverflowError):continue
    return by_key

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS sector_benchmark_snapshot(
        id INTEGER PRIMARY KEY CHECK(id=1),captured_at TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,instant=None,loader=backend_json):
    if not permitted():return False
    instant=instant or datetime.now(timezone.utc);today=instant.astimezone(IST).date()
    report=analyze(loader("/api/v1/market-data/sector-benchmarks"),loader("/api/v1/market-data/strategy-calendar?exchange=NSE"),today)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO sector_benchmark_snapshot VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
            WHERE excluded.captured_at>=sector_benchmark_snapshot.captured_at""",(instant.isoformat(),json.dumps(report,allow_nan=False)))
    return bool(report)

def attach(snapshot,connect,instant):
    summary={"status":"DISABLED_OR_NOT_AUTHORIZED","items":{},"configured_count":len(KEYS),"available_count":0,"notice":NOTICE}
    snapshot["official_sector_benchmarks"]=summary
    if not snapshot.get("enabled") or not permitted():return snapshot
    summary["status"]="AWAITING_EVIDENCE"
    with closing(connect()) as db:
        _table(db);row=db.execute("SELECT * FROM sector_benchmark_snapshot WHERE id=1").fetchone()
    if not row:return snapshot
    stamp=datetime.fromisoformat(row["captured_at"])
    if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=2) or stamp.astimezone(IST).date()!=instant.astimezone(IST).date():return snapshot
    items=json.loads(row["payload"])
    summary.update(items=items,available_count=len(items),status="OBSERVED_INDEX_WINDOWS" if items else "AWAITING_EVIDENCE")
    return snapshot

def compare(row,labels,indexes,today):
    if row.get("exchange")!="NSE" or not exact_isin(row.get("isin")):return None
    key=mapping(labels)
    if not key:return None
    index=indexes.get(key) or {}
    if index.get("benchmark_key")!=key or index.get("calendar_checked_on")!=today.isoformat() or index.get("as_of")!=row.get("as_of"):return None
    windows={}
    for n in relative_strength.WINDOWS:
        k=str(n)
        s=(row.get("comparative_price_windows") or {}).get(k) or {}
        b=(index.get("windows") or {}).get(k) or {}
        if s.get("source_code")!="UPSTOX" or not isinstance(s.get("dates_digest"),str) or len(s["dates_digest"])!=64 or any(s.get(f)!=b.get(f) for f in ("dates_digest","first_date","last_date")) or s.get("last_date")!=row.get("as_of"):continue
        stock,benchmark=s.get("return_percent"),b.get("return_percent")
        if not all(type(x) in (float,int) and isfinite(x) and -100<x<=1e9 for x in (stock,benchmark)):continue
        windows[k]={"stock_return_percent":stock,"index_return_percent":benchmark,"difference_pp":round(stock-benchmark,4),
                    "first_date":b["first_date"],"last_date":b["last_date"]}
    if not windows:return None
    return {"status":"MATCHED_OFFICIAL_SECTOR_PRICE_INDEX","benchmark_key":key,"isin":row["isin"],"exchange":"NSE","id":row["id"],
            "as_of":row["as_of"],"classification_basis":list(labels),"windows":windows,"notice":NOTICE}

def attach_candidates(snapshot,classification,today):
    index=(snapshot.get("official_sector_benchmarks") or {}).get("items") or {}
    rows={}
    for section in snapshot.get("sections",[]):
        if section.get("section")!="NSE" or section.get("status")!="READY":continue
        result=section.get("result") or {};coverage=result.get("discovery_coverage") or {}
        if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":continue
        for row in result.get("company_research_universe",[]):
            if row.get("exchange")!="NSE" or row.get("as_of")!=coverage.get("expected_session") or not exact_isin(row.get("isin")) or type(row.get("id")) is not int:continue
            key=row["isin"]
            if key in rows:rows[key]=None
            else:rows[key]=row
    for item,isin in automatic_company_evidence.identify_priority(snapshot):
        item.pop("official_sector_benchmark",None)
        row=rows.get(isin)
        if row and row["id"]==item.get("id") and row["as_of"]==item.get("as_of") and item["exchange"]=="NSE":
            report=compare(row,classification.get(isin),index,today)
            if report:item["official_sector_benchmark"]=report
    return snapshot
