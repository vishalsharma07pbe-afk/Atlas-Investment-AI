"""Narrow publisher-specific public monthly factsheet adapter, no guessed links.

PPFAS HTML factsheet layout observed November 2026. Exact scheme heading and
AMFI NAV date/value reconciliation required before any fund attachment.
Base expense ratio is not TER; named holdings are not ISIN-level evidence.
"""
from calendar import monthrange
from contextlib import closing
from datetime import date,datetime,timedelta
from decimal import Decimal,InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import json
import os
import re
import sqlite3
import stat
import time
import httpx
from . import nav_catalog,fund_local_evidence as local

VERSION="PPFAS-FACTSHEET-1"
PATH=Path("/app/fund-evidence/amc-factsheet-sources.json")
IST=ZoneInfo("Asia/Kolkata")
MAX_BYTES=5_000_000
NAMES={"Parag Parikh Flexi Cap Fund":"FLEXI_CAP","Parag Parikh Large Cap Fund":"LARGE_CAP"}
BENCHMARKS={"NIFTY 500 (TRI)":"NIFTY 500 TRI","NIFTY 100 (TRI)":"NIFTY 100 TRI"}
NOTICE=("Publisher monthly factsheet observations, reconciled to the exact AMFI Direct Growth NAV date and amount. "
        "Base expense ratio is not total expense ratio. Named holdings/asset allocations are not independent exact-ISIN portfolio evidence. "
        "Current benchmark is not a verified historical mandate. No forward forecast or qualification promotion.")

def permitted():
    return os.getenv("ATLAS_MF_OFFICIAL_AMC_ENABLED","false").lower()=="true" and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"

def month(url,today):
    if not isinstance(url,str) or len(url)>250:raise ValueError("SOURCE_URL")
    p=urlsplit(url)
    m=re.fullmatch(r"/downloads/digital-factsheet/(20[0-9]{2})/([a-z]+)-(20[0-9]{2})/(?:index\.php)?",p.path)
    if p.scheme!="https" or p.netloc!="amc.ppfas.com" or p.query or p.fragment or not m or m[1]!=m[3]:raise ValueError("SOURCE_URL")
    year=int(m[1]);mon=datetime.strptime(m[2],"%B").month
    end=date(year,mon,monthrange(year,mon)[1])
    if not 0<=(today-end).days<=60:raise ValueError("SOURCE_MONTH")
    return end

def sources(today,path=PATH):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>8000:raise ValueError("MANIFEST_SIZE")
        raw=stream.read(8001);after=os.fstat(stream.fileno())
        if len(raw)!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise ValueError("MANIFEST_CHANGED")
    obj=json.loads(raw,object_pairs_hook=local.unique)
    if not isinstance(obj,dict) or obj.get("schema")!=VERSION or obj.get("authorization_attested") is not True:raise ValueError("MANIFEST_SCHEMA")
    urls=obj.get("sources")
    if not isinstance(urls,list) or len(urls)>2:raise ValueError("MANIFEST_LIMIT")
    result={}
    for url in urls:
        d=month(url,today)
        if d in result:raise ValueError("DUPLICATE_MONTH")
        result[d]=url
    return result

class Sections(HTMLParser):
    """Extract only exact scheme heading sections and table rows, no script execution."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=None;self.head=None;self.rows={};self.row=None;self.cell=None;self.count=0;self.ignored=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.ignored+=1
        if self.ignored:return
        if tag=="h2":self.head=[]
        if tag=="tr":self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.ignored:return
        for parts in (self.head,self.cell):
            if parts is not None:
                if sum(map(len,parts))+len(data)>20000:raise ValueError("CELL_LIMIT")
                parts.append(data)
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.ignored:self.ignored-=1;return
        if self.ignored:return
        if tag=="h2" and self.head is not None:
            name=" ".join("".join(self.head).split());self.head=None
            # Other scheme sections must terminate the active section, even
            # when their category is not supported.
            if name.startswith("Parag Parikh "):
                self.active=name if name in NAMES else None
                if self.active:
                    if name in self.rows:raise ValueError("DUPLICATE_SCHEME")
                    self.rows[name]=[]
        if tag in ("td","th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:
            self.count+=1
            if self.count>20000:raise ValueError("ROW_LIMIT")
            if self.active and self.row:self.rows[self.active].append(self.row)
            self.row=None;self.cell=None

def number(value,percent=False):
    if not isinstance(value,str):raise ValueError("NUMBER")
    value=value.strip()
    if percent:
        if not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,6})?%\*?",value):raise ValueError("PERCENT")
        value=value.rstrip("*%")
    elif not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,8})?",value):raise ValueError("NUMBER")
    n=Decimal(value)
    if not n.is_finite() or not 0<=n<= (100 if percent else 1_000_000_000):raise ValueError("RANGE")
    return n

def risk(value):
    value=re.sub(r"[^A-Z]+","_",value.upper()).strip("_").removesuffix("_RISK")
    if value not in local.RISKOMETERS:raise ValueError("RISK")
    return value

def parse(raw,url,today):
    end=month(url,today)
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError("SIZE")
    p=Sections();p.feed(raw.decode("utf-8-sig"));p.close()
    output={}
    for name,rows in p.rows.items():
        def single(label,width):
            matches=[r[1:] for r in rows if len(r)==width+1 and r[0]==label]
            if len(matches)!=1:raise ValueError("AMBIGUOUS_FIELD")
            return matches[0]
        try:
            benchmark=BENCHMARKS[single("Benchmark Name:",1)[0].upper()]
            # NAV heading is a single row preceding exact plan rows.
            nav_headers=[i for i,r in enumerate(rows) if len(r)==1 and r[0].startswith("NAV as on ")]
            if len(nav_headers)!=1:raise ValueError("NAV_DATE")
            i=nav_headers[0];nav_date=datetime.strptime(rows[i][0].removeprefix("NAV as on ").rstrip(":"),"%B %d, %Y").date()
            if not 0<=(end-nav_date).days<=7:raise ValueError("NAV_DATE")
            navs=[r[1] for r in rows[i+1:i+6] if len(r)==2 and r[0]=="Direct Plan - Growth"]
            if len(navs)!=1 or number(navs[0])<=0:raise ValueError("NAV")
            # Current risk table must explicitly name both scheme and benchmark.
            risk_tables=[j for j,r in enumerate(rows) if r==["Change in","Previous Month","Current Month"] and j+2<len(rows) and rows[j+1][0]=="Scheme" and rows[j+2][0]=="Benchmark"]
            if len(risk_tables)!=1:raise ValueError("RISK_TABLE")
            j=risk_tables[0]
            if len(rows[j+1])!=3 or len(rows[j+2])!=3:raise ValueError("RISK_TABLE")
            scheme_risk=risk(rows[j+1][2]);benchmark_risk=risk(rows[j+2][2])
            # October 2026 publisher layout explicitly labels the three-column
            # expense change table as Base Expense Ratio. Verify both copies.
            fee=[r[1:] for r in rows if len(r)==3 and r[0]=="Direct Plan:"]
            displayed=[r[1] for r in rows if len(r)==2 and r[0]=="Direct Plan:"]
            base=None
            if len(fee)==1 and len(displayed)==1 and number(fee[0][1],True)==number(displayed[0],True):
                base=float(number(fee[0][1],True))
            output[name]={"scheme_name":name,"category":NAMES[name],"portfolio_date":end.isoformat(),
                "nav_date":nav_date.isoformat(),"nav":str(number(navs[0])),"benchmark":benchmark,
                "riskometer":scheme_risk,"benchmark_riskometer":benchmark_risk,"base_expense_percent":base,
                "ter_percent":None,"source_url":url,"source_sha256":sha256(raw).hexdigest(),"methodology":VERSION}
        except (ValueError,KeyError,TypeError,IndexError,InvalidOperation):continue
    if not output:raise ValueError("NO_SUPPORTED_SCHEMES")
    return output

def fetch(url,today):
    month(url,today);data=bytearray();deadline=time.monotonic()+30
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=False) as client:
        with client.stream("GET",url,headers={"Accept":"text/html","User-Agent":"ATLAS-Research/2.0"}) as response:
            response.raise_for_status()
            for part in response.iter_bytes():
                if time.monotonic()>deadline or len(data)+len(part)>MAX_BYTES:raise ValueError("DOWNLOAD_LIMIT")
                data.extend(part)
    return bytes(data)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS official_amc_factsheets(
      url TEXT PRIMARY KEY,attempted_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT)""")

def refresh(instant,*,path=PATH,loader=fetch,connect=None):
    if not permitted():return False
    connect=connect or nav_catalog._connect;today=instant.astimezone(IST).date()
    try:links=sources(today,path)
    except (OSError,ValueError,TypeError,KeyError):return False
    if not links:return False
    url=links[max(links)]
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db);old=db.execute("SELECT * FROM official_amc_factsheets WHERE url=?",(url,)).fetchone()
    if old and old["attempted_at"]>(instant-timedelta(hours=24)).isoformat():return old["status"]=="AVAILABLE"
    result=None
    try:result=parse(loader(url,today),url,today)
    except (ValueError,TypeError,KeyError,OSError,httpx.HTTPError):pass
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO official_amc_factsheets VALUES(?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          attempted_at=excluded.attempted_at,status=excluded.status,payload=excluded.payload
          WHERE excluded.attempted_at>=official_amc_factsheets.attempted_at""",
          (url,instant.isoformat(),"AVAILABLE" if result else "UNAVAILABLE",json.dumps(result,allow_nan=False) if result else None))
        db.execute("DELETE FROM official_amc_factsheets WHERE attempted_at<?",((instant-timedelta(days=90)).isoformat(),))
    return bool(result)

def matched(candidates,source_rows,instant,*,path=PATH,connect=None):
    """No fuzzy names, no provider calls; exact code/ISIN and AMFI NAV history."""
    if not permitted():return {}
    connect=connect or nav_catalog._connect;today=instant.astimezone(IST).date()
    try:
        links=sources(today,path)
        if not links:return {}
        url=links[max(links)]
        result={}
        with nav_catalog._LOCK,closing(connect()) as db:
            _table(db);saved=db.execute("SELECT * FROM official_amc_factsheets WHERE url=? AND status='AVAILABLE'",(url,)).fetchone()
            if not saved:return {}
            stamp=datetime.fromisoformat(saved["attempted_at"])
            if not timedelta(0)<=instant-stamp<=timedelta(hours=48):return {}
            observed=json.loads(saved["payload"])
            for f in candidates:
                if f.plan!="DIRECT" or f.option!="GROWTH":continue
                matches=[r for r in source_rows if str(r.get("scheme_code"))==f.identifier]
                if len(matches)!=1:continue
                row=matches[0];isin=row.get("isin_growth")
                if not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin) or row.get("amfi_plan")!="DIRECT" or row.get("amfi_option")!="GROWTH":continue
                name=" ".join(f.name.casefold().replace("-"," ").split())
                keys=[k for k in NAMES if name in (k.casefold()+" direct plan growth",k.casefold()+" direct growth")]
                if len(keys)!=1:continue
                e=observed.get(keys[0])
                if not e or e.get("category")!=f.category or e.get("source_url")!=url or e.get("methodology")!=VERSION:continue
                identity=db.execute("SELECT isin_growth FROM nav_schemes WHERE scheme_code=? AND source='AMFI'",(int(f.identifier),)).fetchone()
                if not identity or identity[0]!=isin:continue
                nav=db.execute("SELECT nav FROM nav_history WHERE scheme_code=? AND nav_date=? AND source='AMFI'",(int(f.identifier),e["nav_date"])).fetchone()
                if not nav or Decimal(nav[0])!=Decimal(e["nav"]):continue
                result[f.identifier]={**e,"scheme_code":f.identifier,"isin_growth":isin,"retrieved_at":saved["attempted_at"],
                    "status":"PUBLISHER_FACTSHEET_NAV_RECONCILED","qualified":False,"notice":NOTICE}
        return result
    except (OSError,ValueError,TypeError,KeyError,AttributeError,InvalidOperation,sqlite3.Error):return {}
