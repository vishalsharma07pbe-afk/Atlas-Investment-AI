"""Opt-in international index and metal observations; independent series caches."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
import json
import os

from .global_macro import _download

INTERVAL=21600
JOBS={"GLOBAL_"+key:key for key in ("SP500","DJIA","NASDAQCOM","NIKKEI225","GOLD","SILVER")}
# FRED IDs are fixed series, not interchangeable ticker symbols.
FIELDS={
    "SP500":("S&P 500","S&P DJI via FRED","INDEX_POINTS","America/New_York","SP500"),
    "DJIA":("Dow Jones Industrial Average","S&P DJI via FRED","INDEX_POINTS","America/New_York","DJIA"),
    "NASDAQCOM":("Nasdaq Composite","Nasdaq via FRED","INDEX_POINTS","America/New_York","NASDAQCOM"),
    "NIKKEI225":("Nikkei 225","Nikkei via FRED","INDEX_POINTS","Asia/Tokyo","NIKKEI225"),
    "GOLD":("Gold spot / USD","Twelve Data","USD_PROVIDER_QUOTE","UTC","XAU/USD"),
    "SILVER":("Silver spot / USD","Twelve Data","USD_PROVIDER_QUOTE","UTC","XAG/USD"),
}
NOTICE=("Prior local-calendar-date published index closes and provider metal daily closes, not live quotes. "
        "FRED series may be copyrighted; Twelve Data coverage depends on plan and rights. No redistribution. "
        "Each series has independent observation dates, not synchronized global sessions. "
        "Changes use available observations; index changes are not total returns. Metal units are provider USD quotes, "
        "not Indian retail prices. No causal market impact or prediction.")

def permitted(key):
    if key not in FIELDS or os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()!="true":
        return False
    allowed={s.strip() for s in os.getenv("ATLAS_GLOBAL_MARKETS_SERIES","").split(",")}
    credential="FRED_API_KEY" if FIELDS[key][2]=="INDEX_POINTS" else "TWELVE_DATA_API_KEY"
    return key in allowed and bool(os.getenv(credential,"").strip())

def _add(output,seen,day,value,today):
    d=date.fromisoformat(day)
    if not today-timedelta(days=90)<=d<today or day in seen or d.isoformat()!=day:
        raise ValueError("GLOBAL_MARKET_DATE_INVALID")
    seen.add(day)
    if value in (None,"","."):
        return
    if isinstance(value,bool) or not isinstance(value,(str,int,float)) or len(str(value))>40:
        raise ValueError("GLOBAL_MARKET_VALUE_INVALID")
    try:
        n=Decimal(str(value))
        if not n.is_finite() or not Decimal("0.000001")<=n<=Decimal("1000000000"):
            raise ValueError("GLOBAL_MARKET_VALUE_INVALID")
    except InvalidOperation:
        raise ValueError("GLOBAL_MARKET_VALUE_INVALID") from None
    output[day]=str(n)

def parse_fred(payload,today):
    data=json.loads(payload)
    rows=data["observations"]
    if data.get("units")!="lin" or not isinstance(rows,list) or not 1<=len(rows)<=100 or data.get("offset")!=0 or data.get("count")!=len(rows):
        raise ValueError("FRED_INCOMPLETE_OR_TRANSFORMED_RESPONSE")
    if data.get("observation_start")!=(today-timedelta(days=90)).isoformat() or data.get("observation_end")!=(today-timedelta(days=1)).isoformat():
        raise ValueError("FRED_DATE_SCOPE_MISMATCH")
    output={}
    seen=set()
    for row in rows:
        _add(output,seen,row["date"],row["value"],today)
    if not output:
        raise ValueError("GLOBAL_MARKET_NO_OBSERVATIONS")
    return output

def parse_metals(payload,key,today):
    data=json.loads(payload)
    meta=data.get("meta") or {}
    rows=data.get("values")
    if (data.get("status")!="ok" or meta.get("symbol")!=FIELDS[key][4] or meta.get("interval")!="1day"
            or meta.get("type")!="Commodity" or not isinstance(rows,list) or not 1<=len(rows)<=100):
        raise ValueError("METAL_IDENTITY_OR_INTERVAL_INVALID")
    # USD is explicit in the exact quoted pair. Never convert or infer ounce size.
    output={}
    seen=set()
    for row in rows:
        _add(output,seen,row["datetime"],row["close"],today)
    if not output:
        raise ValueError("GLOBAL_MARKET_NO_OBSERVATIONS")
    return output

def collect(key,today):
    start=(today-timedelta(days=90)).isoformat()
    end=(today-timedelta(days=1)).isoformat()
    symbol=FIELDS[key][4]
    if FIELDS[key][2]=="INDEX_POINTS":
        params={"series_id":symbol,"api_key":os.environ["FRED_API_KEY"].strip(),"file_type":"json"}
        metadata=json.loads(_download("https://api.stlouisfed.org/fred/series",params))
        rows=metadata.get("seriess")
        if not isinstance(rows,list) or len(rows)!=1 or rows[0].get("id")!=symbol or rows[0].get("frequency_short")!="D" or rows[0].get("units")!="Index":
            raise ValueError("FRED_SERIES_IDENTITY_INVALID")
        return parse_fred(_download("https://api.stlouisfed.org/fred/series/observations",{
            **params,"observation_start":start,"observation_end":end,"units":"lin","limit":100,"sort_order":"asc"}),today)
    return parse_metals(_download("https://api.twelvedata.com/time_series",{
        "symbol":symbol,"interval":"1day","start_date":start,"end_date":end,"outputsize":100,
        "apikey":os.environ["TWELVE_DATA_API_KEY"].strip()}),key,today)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS global_market_snapshot(
        series TEXT PRIMARY KEY,captured_at TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,key,instant=None,loader=collect):
    if not permitted(key):
        return
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo(FIELDS[key][3])).date()
    rows=loader(key,today)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO global_market_snapshot VALUES(?,?,?)
          ON CONFLICT(series) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
          WHERE excluded.captured_at>=global_market_snapshot.captured_at""",
          (key,instant.isoformat(),json.dumps(rows,allow_nan=False)))

def summarize(key,rows,today):
    label,source,unit,_,_=FIELDS[key]
    item={"series":key,"label":label,"source":source,"unit":unit,
          "status":"STALE_OR_MISSING","as_of":None,"value":None,"changes":[]}
    dates=sorted(rows,reverse=True)
    if not dates or not 1<=(today-date.fromisoformat(dates[0])).days<=7:
        return item
    latest=dates[0]
    value=Decimal(rows[latest])
    item.update(status="AVAILABLE",as_of=latest,value=float(value))
    for count,max_days in ((1,7),(5,14),(20,45)):
        if len(dates)<=count:
            continue
        selected=dates[:count+1]
        if (date.fromisoformat(latest)-date.fromisoformat(selected[-1])).days>max_days or any(
            (date.fromisoformat(a)-date.fromisoformat(b)).days>7 for a,b in zip(selected,selected[1:])):
            continue
        item["changes"].append({"observations":count,"start_date":selected[-1],"end_date":latest,
             "percent":float(round(100*(value/Decimal(rows[selected[-1]])-1),4))})
    return item

def read(connect,instant=None):
    instant=instant or datetime.now(timezone.utc)
    items=[]
    with closing(connect()) as db:
        _table(db)
        for key,(label,source,unit,tz,_) in FIELDS.items():
            item={"series":key,"label":label,"source":source,"unit":unit,
                  "status":"DISABLED_OR_NOT_AUTHORIZED","as_of":None,"value":None,"changes":[]}
            items.append(item)
            if not permitted(key):
                continue
            item["status"]="AWAITING_EVIDENCE"
            row=db.execute("SELECT captured_at,payload FROM global_market_snapshot WHERE series=?",(key,)).fetchone()
            if not row:
                continue
            try:
                stamp=datetime.fromisoformat(row["captured_at"])
                if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
                    item["status"]="STALE_CAPTURE"
                    continue
                item.update(summarize(key,json.loads(row["payload"]),instant.astimezone(ZoneInfo(tz)).date()),retrieved_at=stamp.isoformat())
            except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation,ArithmeticError):
                item["status"]="INVALID_CACHED_EVIDENCE"
    count=sum(i["status"]=="AVAILABLE" for i in items)
    return {"status":"AVAILABLE" if count==len(items) else "PARTIAL" if count else "UNAVAILABLE",
            "items":items,"notice":NOTICE}
