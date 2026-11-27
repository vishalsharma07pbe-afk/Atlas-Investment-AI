"""Independent NSE regulatory-indicator capture, positive warnings only.

Legacy 29-field layout documented by NSE. The newer REG1 schema and current
download availability require authorized live acceptance. The file lacks ISIN;
a unique current registry symbol match is explicitly not historical identity proof.
"""
import csv
import io
import json
import os
import re
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from zoneinfo import ZoneInfo
import httpx
from .market_client import backend_json
from .replay_evidence import exact_isin

IST=ZoneInfo("Asia/Kolkata")
INTERVAL=14400
MAX_BYTES=4_000_000
BASE="https://nsearchives.nseindia.com/archives/equities/mkt/"
SPEC="https://nsearchives.nseindia.com/web/sites/default/files/inline-files/REG_INDDDMMYY_File%20Structure%201.pdf"
NOTICE="NSE legacy regulatory indicator, dated for the following trading session. Current unique registry symbol/series match only; source has no ISIN. Positive cautions are review prompts, not findings of misconduct. No negative clearance, BSE coverage or verified pledge percentage. New REG1 schema and live download availability not certified."
# Position indices are zero-based. 100 means not applicable to that indicator.
INDICATORS={5:("GSM",{0,1,2,3,4,6}),6:("LONG_TERM_ASM",{1,2,3,4}),
  7:("UNSOLICITED_SMS",{0,1}),8:("INSOLVENCY",{0,1,2}),9:("SHORT_TERM_ASM",{1,2}),
  10:("DEFAULT_DISCLOSURE",{0,1}),11:("ICA",{0,1}),14:("PROMOTER_PLEDGE_MEASURE",{1}),
  15:("ADD_ON_PRICE_BAND",{1}),16:("TOTAL_PLEDGE_MEASURE",{1}),17:("SOCIAL_MEDIA_SURVEILLANCE",{2}),
  18:("ESM",{1,2}),19:("LOSS_MAKING",{0}),20:("ENCUMBRANCE_THRESHOLD",{0}),
  21:("BZ_SZ_NONCOMPLIANCE",{0}),22:("LISTING_FEE_CAUTION",{0}),24:("DERIVATIVES_EXIT",{0})}
def permitted():
    return os.getenv("ATLAS_NSE_SURVEILLANCE_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def prior_session(calendar,today):
    if calendar.get("exchange")!="NSE" or calendar.get("through")!=(today-timedelta(days=1)).isoformat():return None
    rows=calendar.get("days")
    if not isinstance(rows,list) or len(rows)>1100:return None
    indexed={}
    for row in rows:
        day=row.get("trade_date")
        if day in indexed:return None
        indexed[day]=row.get("state")
    for n in range(1,8):
        day=today-timedelta(days=n)
        state=indexed.get(day.isoformat())
        if state=="REGULAR":return day
        if state!="CLOSED":return None
    return None

def url_for(day):
    return BASE+"REG_IND"+day.strftime("%d%m%y")+".csv"

def parse(payload):
    if not 0<len(payload)<=MAX_BYTES:raise ValueError("SURVEILLANCE_BYTES")
    rows=csv.reader(io.StringIO(payload.decode("utf-8-sig"),newline=""),strict=True)
    result={}
    for n,raw in enumerate(rows):
        if n>=20001:raise ValueError("SURVEILLANCE_ROW_LIMIT")
        row=[v.strip() for v in raw]
        # Accept the documented positional legacy schema only. No guessed
        # layout, unknown newer columns, free prose or partial row recovery.
        if len(row)!=29 or any(len(v)>160 for v in row):raise ValueError("SURVEILLANCE_SCHEMA")
        if n==0 and [v.lower().replace(" ","").replace("_","") for v in row[:5]]==["scripcode","symbol","nseexclusive","status","series"]:
            continue
        code,symbol,exclusive,state,series=row[:5]
        if (not re.fullmatch(r"[0-9]{0,10}",code) or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",symbol)
          or exclusive not in ("Y","N") or state not in ("A","S","I") or not re.fullmatch(r"[A-Z0-9]{1,2}",series)):
            raise ValueError("SURVEILLANCE_IDENTITY")
        key=(symbol,series)
        if key in result:raise ValueError("SURVEILLANCE_DUPLICATE")
        findings=[]
        if state!="A":findings.append("NSE_REPORTED_"+("SUSPENDED" if state=="S" else "INACTIVE"))
        if series in ("BE","BZ","SZ"):findings.append("NSE_REPORTED_RESTRICTED_SERIES_"+series)
        for idx,(name,allowed) in INDICATORS.items():
            if not re.fullmatch(r"[0-9]{1,3}",row[idx]):raise ValueError("SURVEILLANCE_INDICATOR")
            value=int(row[idx])
            if value==100:continue
            if value not in allowed:raise ValueError("SURVEILLANCE_UNKNOWN_INDICATOR")
            findings.append("NSE_REPORTED_"+name+"_INDICATOR_"+str(value))
        result[key]={"symbol":symbol,"series":series,"findings":findings}
    # A malformed/truncated response must never replace the last valid capture.
    if len(result)<100:raise ValueError("SURVEILLANCE_INCOMPLETE")
    return list(result.values())

def download(url):
    data=bytearray()
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        with client.stream("GET",url,headers={"User-Agent":"ATLAS-Research/2.0"}) as response:
            if response.status_code!=200:return None
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data)>MAX_BYTES:raise ValueError("SURVEILLANCE_BYTES")
    return bytes(data)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS nse_regulatory_capture(
      id INTEGER PRIMARY KEY CHECK(id=1),report_date TEXT NOT NULL,retrieved_at TEXT NOT NULL,
      digest TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,instant=None,calendar_loader=backend_json,loader=download):
    if not permitted():return False
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    day=prior_session(calendar_loader("/api/v1/market-data/strategy-calendar?exchange=NSE"),today)
    if day is None:return False
    with closing(connect()) as db:
        _table(db)
        old=db.execute("SELECT report_date FROM nse_regulatory_capture WHERE id=1").fetchone()
    if old and old["report_date"]==day.isoformat():return True
    payload=loader(url_for(day))
    if payload is None:return False
    rows=parse(payload)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO nse_regulatory_capture VALUES(1,?,?,?,?)
         ON CONFLICT(id) DO UPDATE SET report_date=excluded.report_date,retrieved_at=excluded.retrieved_at,
         digest=excluded.digest,payload=excluded.payload WHERE excluded.report_date>nse_regulatory_capture.report_date""",
         (day.isoformat(),instant.isoformat(),sha256(payload).hexdigest(),json.dumps(rows)))
    return True

def attach(snapshot,connect,instant):
    summary={"status":"DISABLED_OR_NOT_AUTHORIZED","notice":NOTICE,"matched_positive_count":0}
    snapshot["exchange_surveillance"]=summary
    if not snapshot.get("enabled") or not permitted():return snapshot
    summary["status"]="AWAITING_SOURCE"
    with closing(connect()) as db:
        _table(db)
        saved=db.execute("SELECT * FROM nse_regulatory_capture WHERE id=1").fetchone()
    if not saved:return snapshot
    today=instant.astimezone(IST).date()
    day=date.fromisoformat(saved["report_date"])
    retrieved=datetime.fromisoformat(saved["retrieved_at"])
    if retrieved.tzinfo is None or retrieved>instant or not 1<=(today-day).days<=7:return snapshot
    sections=[s for s in snapshot.get("sections",[]) if s.get("section")=="NSE" and s.get("status")=="READY"]
    if len(sections)!=1:return snapshot
    result=sections[0].get("result") or {};coverage=result.get("discovery_coverage") or {}
    if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":return snapshot
    current=coverage.get("expected_session")==day.isoformat()
    rows=json.loads(saved["payload"])
    indexed={}
    for row in rows:indexed.setdefault(row["symbol"],[]).append(row)
    observed=result.get("venue_observations") or []
    symbols={}
    for row in observed:
        if row.get("exchange")=="NSE" and exact_isin(row.get("isin")):
            symbols.setdefault(row.get("symbol"),set()).add((row["isin"],row.get("id")))
    targets=list(observed)+list(result.get("steady_momentum_candidates") or [])
    for group in (result.get("horizons") or {}).values():targets.extend(group.get("candidates",[]))
    count=set()
    for row in targets:
        row.pop("exchange_surveillance",None)
        symbol=row.get("symbol");isin=row.get("isin");identity=(isin,row.get("id"))
        if row.get("exchange")!="NSE" or symbols.get(symbol)!={identity}:continue
        records=indexed.get(symbol,[])
        matches=[r for r in records if r["series"]=="EQ"]
        # Different series or absent row cannot be equated to clearance.
        findings=list(matches[0]["findings"]) if len(matches)==1 else []
        if any(r["series"] in ("BE","BZ","SZ") for r in records):
            findings.append("NSE_SYMBOL_OTHER_RESTRICTED_SERIES_REVIEW")
        if not findings:continue
        count.add(isin)
        row["exchange_surveillance"]={"status":"REPORTED_CAUTION_CURRENT_FILE" if current else "REPORTED_CAUTION_OLDER_FILE",
          "source_exchange":"NSE","report_date":day.isoformat(),"retrieved_at":retrieved.isoformat(),"source_url":url_for(day),
          "source_sha256":saved["digest"],"matched_symbol":symbol,"source_series":[r["series"] for r in records],
          "findings":sorted(set(findings)),"notice":NOTICE}
    summary.update(status="CURRENT_FILE_OBSERVED" if current else "OLDER_FILE_RETAINED",report_date=day.isoformat(),
        retrieved_at=retrieved.isoformat(),source_url=url_for(day),matched_positive_count=len(count),row_count=len(rows))
    return snapshot
