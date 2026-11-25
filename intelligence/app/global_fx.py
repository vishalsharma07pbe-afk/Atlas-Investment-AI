"""Bounded official ECB reference-rate context, no executable quote or forecast."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from time import monotonic
from zoneinfo import ZoneInfo
import csv
import io
import json
import os
import httpx

INTERVAL=21600
MAX_BYTES=512000
CURRENCIES=("USD","INR","GBP","JPY","CNY")
URL="https://data-api.ecb.europa.eu/service/data/EXR/D.USD+INR+GBP+JPY+CNY.EUR.SP00.A"
SOURCE="European Central Bank"
SOURCE_PAGE="https://data.ecb.europa.eu/help/api/data-examples"
PAIRS=(("EUR","USD"),("EUR","INR"),("USD","INR"),("GBP","INR"),("JPY","INR"),("CNY","INR"))
NOTICE=("European Central Bank daily reference rates for information only. ATLAS calculates cross-rates and percentage changes; "
        "not executable quotes, not Indian closing prices, not a session-continuity audit or a market forecast. "
        "Changes compare matched available observation dates, not assumed trading sessions. "
        "Commodity prices, international equity indices and macro releases require separate authorized sources.")

def permitted():
    return (os.getenv("ATLAS_GLOBAL_FX_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true")

def parse(payload,today):
    if len(payload)>MAX_BYTES:
        raise ValueError("FX_RESPONSE_LIMIT")
    reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig"),newline=""))
    required={"FREQ","CURRENCY","CURRENCY_DENOM","EXR_TYPE","EXR_SUFFIX","TIME_PERIOD","OBS_VALUE"}
    if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)) or not required.issubset(reader.fieldnames):
        raise ValueError("FX_SCHEMA_CHANGED")
    result={key:{} for key in CURRENCIES}
    seen=set()
    for index,row in enumerate(reader,1):
        if index>1000 or None in row or any(v is None for v in row.values()):
            raise ValueError("FX_ROW_LIMIT_OR_SHAPE")
        key=row["CURRENCY"]
        if key not in result or (row["FREQ"],row["CURRENCY_DENOM"],row["EXR_TYPE"],row["EXR_SUFFIX"])!=("D","EUR","SP00","A"):
            raise ValueError("FX_SERIES_MISMATCH")
        day=date.fromisoformat(row["TIME_PERIOD"])
        if not today-timedelta(days=95)<=day<=today or (key,day) in seen:
            raise ValueError("FX_DATE_OR_DUPLICATE")
        seen.add((key,day))
        raw=row["OBS_VALUE"]
        if not raw or raw==".":
            continue
        try:
            value=Decimal(raw)
            if not value.is_finite() or not Decimal("0.000001")<=value<=Decimal("1000000"):
                raise ValueError("FX_INVALID_VALUE")
        except InvalidOperation as exc:
            raise ValueError("FX_INVALID_VALUE") from exc
        result[key][day.isoformat()]=str(value)
    if not any(result.values()):
        raise ValueError("FX_NO_OBSERVATIONS")
    return result

def download(today):
    params={"format":"csvdata","detail":"dataonly","startPeriod":(today-timedelta(days=90)).isoformat(),
            "endPeriod":today.isoformat()}
    data=bytearray()
    deadline=monotonic()+30
    with httpx.Client(timeout=15,follow_redirects=False,headers={"Accept-Encoding":"identity","User-Agent":"ATLAS-Research/1.0"}) as client:
        with client.stream("GET",URL,params=params) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                if monotonic()>deadline or len(data)+len(chunk)>MAX_BYTES:
                    raise ValueError("FX_DOWNLOAD_LIMIT")
                data.extend(chunk)
    return bytes(data)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS global_fx_snapshot(
        id INTEGER PRIMARY KEY CHECK(id=1), captured_at TEXT NOT NULL, payload TEXT NOT NULL)""")

def refresh(connect,instant=None,loader=download):
    if not permitted():
        return
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("Europe/Berlin")).date()
    rows=parse(loader(today),today)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO global_fx_snapshot VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
            WHERE excluded.captured_at>=global_fx_snapshot.captured_at""",
            (instant.isoformat(),json.dumps(rows,allow_nan=False)))

def summarize(rows,today):
    items=[]
    for base,quote in PAIRS:
        q=rows.get(quote,{})
        b=rows.get(base,{}) if base!="EUR" else None
        dates=sorted(q.keys() if b is None else q.keys()&b.keys(),reverse=True)
        item={"pair":base+"_"+quote,"status":"UNAVAILABLE","basis":"ECB_EUR_REFERENCE" if b is None else "DERIVED_ECB_CROSS",
              "as_of":None,"rate":None,"changes":[]}
        if not dates:
            items.append(item)
            continue
        latest=dates[0]
        # Never use an older common date when one cross leg is more recent.
        if latest!=max(q) or (b is not None and latest!=max(b)) or not 0<=(today-date.fromisoformat(latest)).days<=5:
            items.append(item)
            continue
        def rate(day):
            return Decimal(q[day])/(Decimal(b[day]) if b is not None else Decimal(1))
        value=rate(latest)
        item.update(status="AVAILABLE",as_of=latest,rate=float(round(value,8)))
        for count,max_days in ((1,7),(5,14),(20,45)):
            if len(dates)<=count:
                continue
            selected=dates[:count+1]
            # A missing leg within a cross-rate interval invalidates it.
            if b is not None and any((d in q)!=(d in b) for d in set(q)|set(b) if selected[-1]<=d<=latest):
                continue
            if (date.fromisoformat(latest)-date.fromisoformat(selected[-1])).days>max_days or any(
                (date.fromisoformat(a)-date.fromisoformat(z)).days>7 for a,z in zip(selected,selected[1:])):
                continue
            item["changes"].append({"observations":count,"start_date":selected[-1],"end_date":latest,
                "percent":float(round(100*(value/rate(selected[-1])-1),4))})
        items.append(item)
    return items

def read(connect,instant=None):
    result={"status":"DISABLED_OR_NOT_AUTHORIZED","source":SOURCE,"source_url":SOURCE_PAGE,"items":[],"notice":NOTICE}
    if not permitted():
        return result
    result["status"]="AWAITING_REFERENCE_RATES"
    instant=instant or datetime.now(timezone.utc)
    with closing(connect()) as db:
        _table(db)
        row=db.execute("SELECT captured_at,payload FROM global_fx_snapshot WHERE id=1").fetchone()
    if not row:
        return result
    stamp=datetime.fromisoformat(row["captured_at"])
    if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
        result["status"]="STALE_CAPTURE"
        return result
    items=summarize(json.loads(row["payload"]),instant.astimezone(ZoneInfo("Europe/Berlin")).date())
    count=sum(item["status"]=="AVAILABLE" for item in items)
    result.update(status="REFERENCE_RATES_AVAILABLE" if count==len(items) else "PARTIAL_REFERENCE_RATES" if count else "STALE_OR_UNMATCHED_OBSERVATIONS",
                  retrieved_at=stamp.isoformat(),items=items)
    return result
