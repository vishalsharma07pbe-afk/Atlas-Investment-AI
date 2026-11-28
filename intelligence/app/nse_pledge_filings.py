"""Opt-in independent issuer-reported quarterly promoter encumbrance research.

Only direct NSE archive iXBRL HTML documents of the inspected Table I layout.
The candidate website JSON index is not a documented API; never bypass a
denial, infer archive URLs, substitute another quarter or assume missing zero.
No individual shareholder names, PANs, raw HTML or provider prose retained.
"""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from calendar import monthrange
from decimal import Decimal,InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urlsplit
from hashlib import sha256
from zoneinfo import ZoneInfo
import json
import os
import re
import httpx
from .replay_evidence import exact_isin
from .company_venues import collect
from .automatic_company_evidence import identify_priority

IST=ZoneInfo("Asia/Kolkata")
INDEX="https://www.nseindia.com/api/corporate-share-holdings-master"
SOURCE="https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern"
INTERVAL=900
MAX_BYTES=5_000_000
NOTICE=("Issuer-reported Regulation 31 quarterly aggregate, separately sourced from NSE. "
        "Percentages use promoter shares held, not total company capital. This is a dated filing observation, "
        "not verified current encumbrance, independent audit, absence of later revisions or investment clearance.")

def permitted():
    return os.getenv("ATLAS_NSE_PLEDGE_FILINGS_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def archive_url(url):
    if not isinstance(url,str) or len(url)>300:return None
    p=urlsplit(url)
    if p.scheme!="https" or p.netloc!="nsearchives.nseindia.com" or p.query or p.fragment:return None
    if not re.fullmatch(r"/corporate/ixbrl/SHP_[A-Za-z0-9_]+_iXBRL_WEB\.html",p.path):return None
    return url

def quarter(value,today):
    d=datetime.strptime(value,"%d-%b-%Y").date()
    if d.month not in (3,6,9,12) or d.day!=monthrange(d.year,d.month)[1] or not 0<=(today-d).days<=150:
        raise ValueError("FILING_PERIOD")
    return d

def choose_index(rows,symbol,today):
    if not isinstance(rows,list) or not 1<=len(rows)<=200:raise ValueError("FILING_INDEX_SCHEMA")
    dated=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError("FILING_INDEX_SCHEMA")
        if row.get("symbol") not in (None,symbol):raise ValueError("FILING_INDEX_SYMBOL")
        try:d=datetime.strptime(row["date"],"%d-%b-%Y").date()
        except (KeyError,ValueError,TypeError):raise ValueError("FILING_INDEX_DATE")
        if d>today:raise ValueError("FUTURE_FILING")
        dated.append((d,row))
    latest=max(d for d,_ in dated)
    quarter(latest.strftime("%d-%b-%Y"),today)
    urls={r.get("xbrl") for d,r in dated if d==latest and isinstance(r.get("xbrl"),str)}
    if len(urls)!=1 or any(not r.get("xbrl") for d,r in dated if d==latest):raise ValueError("FILING_REVISION_AMBIGUOUS")
    url=archive_url(next(iter(urls)))
    if not url:raise ValueError("UNSUPPORTED_FILING_FORMAT")
    return latest,url

class Tables(HTMLParser):
    """Collect bounded cell text. No network, script evaluation or DOM rendering."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.tables=[]
        self.cells=0
    def handle_starttag(self,tag,attrs):
        if tag=="table":
            if len(self.stack)>=8:raise ValueError("FILING_TABLE_DEPTH")
            self.stack.append({"rows":[],"row":None,"cell":None})
        if not self.stack:return
        t=self.stack[-1]
        if tag=="tr":
            t["row"]=[]
        elif tag in ("td","th") and t["row"] is not None:
            self.cells+=1
            if self.cells>100000:raise ValueError("FILING_CELL_LIMIT")
            t["cell"]=[]
    def handle_data(self,data):
        if self.stack and self.stack[-1]["cell"] is not None:
            cell=self.stack[-1]["cell"]
            if sum(map(len,cell))+len(data)>20000:raise ValueError("FILING_CELL_SIZE")
            cell.append(data)
    def handle_endtag(self,tag):
        if not self.stack:return
        t=self.stack[-1]
        if tag in ("td","th") and t["cell"] is not None:
            t["row"].append(" ".join("".join(t["cell"]).split()))
            t["cell"]=None
        elif tag=="tr" and t["row"] is not None:
            t["rows"].append(t["row"]);t["row"]=None;t["cell"]=None
        elif tag=="table":
            self.tables.append(self.stack.pop()["rows"])

def shares(value):
    if not re.fullmatch(r"[0-9]{1,18}",value):raise ValueError("FILING_SHARE_COUNT")
    return int(value)
def percent(value,count,total):
    if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,8})?",value):raise ValueError("FILING_PERCENT")
    p=Decimal(value)
    if not 0<=p<=100:raise ValueError("FILING_PERCENT")
    if abs(p-Decimal(count)*100/Decimal(total))>Decimal("0.02"):raise ValueError("FILING_PERCENT_RECONCILIATION")
    return float(p)

def parse(payload,isin,expected,today):
    if not exact_isin(isin) or not 0<len(payload)<=MAX_BYTES:raise ValueError("FILING_BYTES_OR_IDENTITY")
    parser=Tables()
    parser.feed(payload.decode("utf-8-sig"));parser.close()
    metadata={}
    keys={"ISIN","Class of Security","Type of report","Quarter Ended / Half year ended/Date of Report (For Prelisting / Allotment)",
          "SEBI Regulation under which Shareholding pattern is filed"}
    for table in parser.tables:
        for row in table:
            if len(row)==2 and row[0] in keys:
                if row[0] in metadata:raise ValueError("FILING_DUPLICATE_METADATA")
                metadata[row[0]]=row[1]
    period_key="Quarter Ended / Half year ended/Date of Report (For Prelisting / Allotment)"
    if metadata.get("ISIN")!=isin or metadata.get("Class of Security")!="Equity" or metadata.get("Type of report")!="Quarterly" or metadata.get("SEBI Regulation under which Shareholding pattern is filed")!="Regulation 31 (1)(b)":
        raise ValueError("FILING_IDENTITY_SCOPE")
    if quarter(metadata.get(period_key,""),today)!=expected:raise ValueError("FILING_DATE_MISMATCH")
    candidates=[]
    for table in parser.tables:
        # This specific modern Table I summary has 32 leaf cells; verify
        # distinctive ordered headers before reading a single aggregate row.
        header=[r for r in table if len(r)>=20 and r[:2]==["Category (I)","Category of shareholder (II)"]]
        if not header:continue
        if len(header)!=1:raise ValueError("FILING_HEADER_AMBIGUOUS")
        text=header[0]
        labels=["Number of Locked in shares (XIII)","Number of Shares pledged (XIV)","Non-Disposal Undertaking (XV)","Other encumbrances, if any (XVI)"]
        indexes=[text.index(v) if v in text else -1 for v in labels]
        if min(indexes)<0 or indexes!=sorted(set(indexes)) or not any(v.startswith("Total Number of Shares encumbered (XVII)") for v in text):raise ValueError("FILING_HEADER_CHANGED")
        candidates.extend(r for r in table if r[:2]==["A","Promoter & Promoter Group"])
    if len(candidates)!=1 or len(candidates[0])!=32:raise ValueError("FILING_SUMMARY_LAYOUT")
    r=candidates[0]
    total=shares(r[6])
    if total<=0 or sum(shares(r[i]) for i in (3,4,5))!=total:raise ValueError("FILING_TOTAL")
    values={}
    for key,i in (("pledged",20),("non_disposal",22),("other_encumbrance",24),("total_encumbered",26)):
        count=shares(r[i])
        if count>total:raise ValueError("FILING_COUNT_RANGE")
        values[key+"_shares"]=count
        values[key+"_percent_of_promoter_shares"]=percent(r[i+1],count,total)
    if sum(values[k+"_shares"] for k in ("pledged","non_disposal","other_encumbrance"))!=values["total_encumbered_shares"]:
        raise ValueError("FILING_ENCUMBRANCE_TOTAL")
    return {"isin":isin,"period":expected.isoformat(),"promoter_shares":total,**values}

def fetch(client,url,params=None):
    data=bytearray()
    with client.stream("GET",url,params=params,headers={"User-Agent":"ATLAS-Research/2.0","Accept":"application/json,text/html"}) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise ValueError("FILING_BYTES")
    return bytes(data)

def load(symbol,isin,today):
    # No cookies, access-control bypass, redirects or arbitrary host requests.
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        latest,url=choose_index(json.loads(fetch(client,INDEX,{"index":"equities","symbol":symbol})),symbol,today)
        raw=fetch(client,url)
    return {**parse(raw,isin,latest,today),"source_url":url,"source_sha256":sha256(raw).hexdigest()}

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS nse_pledge_filings(
      isin TEXT PRIMARY KEY,attempted_at TEXT NOT NULL,next_due TEXT NOT NULL,status TEXT NOT NULL,payload TEXT)""")

def refresh(snapshot,connect,instant,loader=load):
    if not snapshot.get("enabled") or not permitted():return False
    today=instant.astimezone(IST).date()
    observations=collect(snapshot,instant)
    targets={}
    for item,isin in identify_priority(snapshot):
        venues=[r for r in observations.get(isin,[]) if r["exchange"]=="NSE" and r.get("as_of")==item.get("as_of")]
        if len(venues)==1 and re.fullmatch(r"[A-Z0-9._&-]{1,40}",venues[0]["symbol"]):
            targets[isin]=venues[0]["symbol"]
    stamp=instant.isoformat()
    with closing(connect()) as db,db:
        _table(db);db.execute("BEGIN IMMEDIATE")
        old={r["isin"]:r for r in db.execute("SELECT * FROM nse_pledge_filings")}
        # Global persisted cooldown after any failed request; no retry storm.
        if any(r["status"] in ("RUNNING","UNAVAILABLE") and r["attempted_at"]>(instant-timedelta(hours=1)).isoformat() for r in old.values()):return False
        due=sorted((i for i in targets if i not in old or old[i]["next_due"]<=stamp),key=lambda i:(old[i]["attempted_at"] if i in old else "",i))
        if not due:return bool(targets)
        isin=due[0]
        db.execute("""INSERT INTO nse_pledge_filings VALUES(?,?,?,'RUNNING',NULL)
          ON CONFLICT(isin) DO UPDATE SET attempted_at=excluded.attempted_at,next_due=excluded.next_due,status='RUNNING',payload=NULL""",
          (isin,stamp,(instant+timedelta(hours=1)).isoformat()))
    result=None
    try:
        result=loader(targets[isin],isin,today)
        if result.get("isin")!=isin or not archive_url(result.get("source_url")):result=None
    except (ValueError,TypeError,KeyError,AttributeError,UnicodeError,httpx.HTTPError,OSError):pass
    with closing(connect()) as db,db:
        _table(db)
        db.execute("UPDATE nse_pledge_filings SET status=?,payload=?,next_due=? WHERE isin=? AND attempted_at=? AND status='RUNNING'",
           ("AVAILABLE" if result else "UNAVAILABLE",json.dumps(result,allow_nan=False) if result else None,
            (instant+timedelta(days=1) if result else instant+timedelta(hours=6)).isoformat(),isin,stamp))
    return result is not None

def attach(snapshot,connect,instant):
    summary={"status":"DISABLED_OR_NOT_AUTHORIZED","notice":NOTICE,"matched_companies":0}
    snapshot["independent_pledge_filings"]=summary
    if not snapshot.get("enabled") or not permitted():return snapshot
    with closing(connect()) as db:
        _table(db)
        saved={r["isin"]:r for r in db.execute("SELECT * FROM nse_pledge_filings WHERE status='AVAILABLE' AND attempted_at BETWEEN ? AND ?",
            ((instant-timedelta(days=7)).isoformat(),instant.isoformat()))}
    matched=set()
    today=instant.astimezone(IST).date()
    for item,isin in identify_priority(snapshot):
        item.pop("independent_pledge_evidence",None)
        if isin not in saved:continue
        try:
            row=saved[isin];e=json.loads(row["payload"])
            period=date.fromisoformat(e["period"])
            if e["isin"]!=isin or not archive_url(e["source_url"]) or not 0<=(today-period).days<=150:continue
        except (ValueError,TypeError,KeyError):continue
        item["independent_pledge_evidence"]={**e,"retrieved_at":row["attempted_at"],"status":"REPORTED_QUARTERLY_AGGREGATE","notice":NOTICE}
        matched.add(isin)
    summary.update(status="REPORTED_FILINGS_AVAILABLE" if matched else "AWAITING_EVIDENCE",matched_companies=len(matched))
    return snapshot
