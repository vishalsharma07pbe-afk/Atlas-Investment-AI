"""Independent official daily oil and nominal Treasury yield observations."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo
import json
import os
import re
import xml.etree.ElementTree as ET

INTERVAL=21600
MAX_BYTES=2_000_000
JOBS={"GLOBAL_OIL":"OIL","GLOBAL_YIELDS":"YIELDS"}
EIA_URL="https://api.eia.gov/v2/petroleum/pri/spt/data/"
TREASURY_URL="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
FIELDS={"OIL":{"RBRTE":"Brent spot crude","RWTC":"WTI spot crude"},
        "YIELDS":{"US2Y":"US 2-year par yield","US10Y":"US 10-year par yield","US30Y":"US 30-year par yield"}}
SOURCES={"OIL":"US EIA","YIELDS":"US Treasury"}
NOTICE=("EIA published spot oil prices (USD per barrel), not futures or executable quotes; publication can lag. "
        "Treasury nominal constant-maturity par yields are percentages; changes are basis points. "
        "Each series has independent dates. Historical changes use available observations, not certified sessions. "
        "No causal Indian market impact, forecast or qualification inference.")

def permitted(source):
    if source not in FIELDS or os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()!="true":
        return False
    flag="ATLAS_GLOBAL_OIL_ENABLED" if source=="OIL" else "ATLAS_GLOBAL_YIELDS_ENABLED"
    return os.getenv(flag,"false").lower()=="true" and (source!="OIL" or bool(os.getenv("EIA_API_KEY","").strip()))

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def _download(url,params):
    # No redirects or HTTP client URL logging (EIA key is a query parameter).
    try:
        request=Request(url+"?"+urlencode(params,doseq=True),headers={"Accept-Encoding":"identity","User-Agent":"ATLAS-Research/1.0"})
        deadline=monotonic()+30
        data=bytearray()
        with build_opener(_NoRedirect()).open(request,timeout=12) as response:
            while True:
                chunk=response.read(65536)
                if monotonic()>deadline or len(data)+len(chunk)>MAX_BYTES:
                    raise ValueError("GLOBAL_SOURCE_LIMIT")
                if not chunk:
                    break
                data.extend(chunk)
        return bytes(data)
    except Exception:
        raise ValueError("GLOBAL_SOURCE_REQUEST_FAILED") from None

def _number(value,source):
    if value is None or value in ("","N/A"):
        return None
    if isinstance(value,bool) or not isinstance(value,(int,float,str,Decimal)) or len(str(value))>40:
        raise ValueError("GLOBAL_VALUE_INVALID")
    try:
        n=Decimal(str(value))
        # Preserve historically possible nonpositive oil prices; percentage
        # change is withheld across nonpositive endpoints or intermediate values.
        low,high=(-1000,10000) if source=="OIL" else (0,100)
        if not n.is_finite() or not low<=n<=high:
            raise ValueError("GLOBAL_VALUE_INVALID")
        return str(n)
    except InvalidOperation:
        raise ValueError("GLOBAL_VALUE_INVALID") from None

def parse_oil(payload,today):
    if len(payload)>MAX_BYTES:
        raise ValueError("GLOBAL_SOURCE_LIMIT")
    response=json.loads(payload)["response"]
    rows=response["data"]
    if not isinstance(rows,list) or not 1<=len(rows)<=200 or str(response.get("total"))!=str(len(rows)):
        raise ValueError("OIL_INCOMPLETE_RESPONSE")
    if response.get("frequency","daily")!="daily":
        raise ValueError("OIL_FREQUENCY_MISMATCH")
    output={s:{} for s in FIELDS["OIL"]}
    seen=set()
    for row in rows:
        key=row["series"]
        day=date.fromisoformat(row["period"])
        if key not in output or row["units"].upper()!="$/BBL" or not today-timedelta(days=90)<=day<=today or (key,day) in seen:
            raise ValueError("OIL_IDENTITY_OR_DATE_INVALID")
        seen.add((key,day))
        value=_number(row["value"],"OIL")
        if value is not None:
            output[key][day.isoformat()]=value
    if not any(output.values()):
        raise ValueError("OIL_NO_OBSERVATIONS")
    return output

ATOM="{http://www.w3.org/2005/Atom}"
META="{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
DATA="{http://schemas.microsoft.com/ado/2007/08/dataservices}"
YIELD_FIELDS={"US2Y":"BC_2YEAR","US10Y":"BC_10YEAR","US30Y":"BC_30YEAR"}

def parse_yields(payload,year,today):
    if len(payload)>MAX_BYTES:
        raise ValueError("GLOBAL_SOURCE_LIMIT")
    raw=payload.decode("utf-8-sig")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper() or "\x00" in raw:
        raise ValueError("UNSAFE_XML")
    root=ET.fromstring(raw)
    if root.tag!=ATOM+"feed" or any(x.get("rel")=="next" for x in root.findall(ATOM+"link")):
        raise ValueError("TREASURY_INCOMPLETE_FEED")
    entries=root.findall(ATOM+"entry")
    if len(entries)>300:
        raise ValueError("TREASURY_ROW_LIMIT")
    output={s:{} for s in FIELDS["YIELDS"]}
    seen=set()
    for entry in entries:
        props=entry.find(ATOM+"content/"+META+"properties")
        if props is None:
            raise ValueError("TREASURY_SCHEMA_INVALID")
        stamp=props.findtext(DATA+"NEW_DATE")
        if not stamp or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.0+)?",stamp):
            raise ValueError("TREASURY_DATE_INVALID")
        day=date.fromisoformat(stamp[:10])
        if day.year!=year or day>today or day in seen:
            raise ValueError("TREASURY_DATE_INVALID")
        seen.add(day)
        for key,field in YIELD_FIELDS.items():
            node=props.find(DATA+field)
            if node is None:
                raise ValueError("TREASURY_SCHEMA_INVALID")
            value=None if node.get(META+"null")=="true" else _number(node.text,"YIELDS")
            if value is not None and day>=today-timedelta(days=90):
                output[key][day.isoformat()]=value
    return output

def collect(source,today):
    start=today-timedelta(days=90)
    if source=="OIL":
        return parse_oil(_download(EIA_URL,{"api_key":os.environ["EIA_API_KEY"].strip(),"frequency":"daily","data[]":"value",
            "facets[series][]":["RWTC","RBRTE"],"start":start.isoformat(),"end":today.isoformat(),"length":200,
            "sort[0][column]":"period","sort[0][direction]":"desc"}),today)
    output={s:{} for s in FIELDS["YIELDS"]}
    for year in sorted({start.year,today.year}):
        values=parse_yields(_download(TREASURY_URL,{"data":"daily_treasury_yield_curve","field_tdr_date_value":year}),year,today)
        for key,series in values.items():
            output[key].update(series)
    if not any(output.values()):
        raise ValueError("TREASURY_NO_OBSERVATIONS")
    return output

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS global_macro_snapshot(
      source TEXT PRIMARY KEY, captured_at TEXT NOT NULL, payload TEXT NOT NULL)""")

def refresh(connect,source,instant=None,loader=collect):
    if not permitted(source):
        return
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("America/New_York")).date()
    rows=loader(source,today)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO global_macro_snapshot VALUES(?,?,?)
          ON CONFLICT(source) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
          WHERE excluded.captured_at>=global_macro_snapshot.captured_at""",
          (source,instant.isoformat(),json.dumps(rows,allow_nan=False)))

def summarize(source,rows,today):
    items=[]
    for key,label in FIELDS[source].items():
        values=rows.get(key,{})
        dates=sorted(values,reverse=True)
        item={"series":key,"label":label,"unit":"PERCENT" if source=="YIELDS" else "USD_PER_BARREL",
              "status":"UNAVAILABLE","as_of":None,"value":None,"changes":[]}
        items.append(item)
        if not dates:
            continue
        latest=dates[0]
        age=(today-date.fromisoformat(latest)).days
        if not 0<=age<=(10 if source=="OIL" else 5):
            item["status"]="STALE_OBSERVATION"
            continue
        value=Decimal(values[latest])
        item.update(status="AVAILABLE",as_of=latest,value=float(value))
        for count,max_days in ((1,7),(5,14),(20,45)):
            if len(dates)<=count:
                continue
            selected=dates[:count+1]
            if (date.fromisoformat(latest)-date.fromisoformat(selected[-1])).days>max_days or any(
                (date.fromisoformat(a)-date.fromisoformat(b)).days>7 for a,b in zip(selected,selected[1:])):
                continue
            prior=Decimal(values[selected[-1]])
            if source=="OIL" and any(Decimal(values[d])<=0 for d in selected):
                continue
            delta=100*(value-prior) if source=="YIELDS" else 100*(value/prior-1)
            item["changes"].append({"observations":count,"start_date":selected[-1],"end_date":latest,
                                    "value":float(round(delta,4)),"unit":"BASIS_POINTS" if source=="YIELDS" else "PERCENT"})
    return items

def read(connect,instant=None):
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("America/New_York")).date()
    sources=[]
    with closing(connect()) as db:
        _table(db)
        for source in FIELDS:
            item={"source":SOURCES[source],"status":"DISABLED_OR_NOT_AUTHORIZED","items":[]}
            sources.append(item)
            if not permitted(source):
                continue
            item["status"]="AWAITING_EVIDENCE"
            row=db.execute("SELECT captured_at,payload FROM global_macro_snapshot WHERE source=?",(source,)).fetchone()
            if not row:
                continue
            stamp=datetime.fromisoformat(row["captured_at"])
            if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
                item["status"]="STALE_CAPTURE"
                continue
            items=summarize(source,json.loads(row["payload"]),today)
            count=sum(v["status"]=="AVAILABLE" for v in items)
            item.update(status="AVAILABLE" if count==len(items) else "PARTIAL" if count else "STALE_OR_MISSING",
                        retrieved_at=stamp.isoformat(),items=items)
    return {"status":"AVAILABLE" if all(s["status"]=="AVAILABLE" for s in sources) else "PARTIAL" if any(s["status"] in ("AVAILABLE","PARTIAL") for s in sources) else "UNAVAILABLE",
            "sources":sources,"notice":NOTICE}
