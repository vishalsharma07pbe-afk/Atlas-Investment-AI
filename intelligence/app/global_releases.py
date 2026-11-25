"""Official public RSS headline evidence, isolated from manual news and trading."""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from urllib.parse import urlsplit,urlunsplit
import json
import os
import re
import xml.etree.ElementTree as ET

from .global_macro import _download

INTERVAL=1800
MAX_BYTES=1_000_000
# Exact URLs from the agencies' published RSS directories.
FIELDS={
    "FED":("Federal Reserve monetary policy","Federal Reserve","US","https://www.federalreserve.gov/feeds/press_monetary.xml","federalreserve.gov"),
    "ECB":("ECB press and communications","European Central Bank","EUROPE","https://www.ecb.europa.eu/rss/press.html","ecb.europa.eu"),
    "BLS_CPI":("US consumer prices","US Bureau of Labor Statistics","US","https://www.bls.gov/feed/cpi.rss","bls.gov"),
    "BLS_PPI":("US producer prices","US Bureau of Labor Statistics","US","https://www.bls.gov/feed/ppi.rss","bls.gov"),
    "BLS_JOBS":("US employment situation","US Bureau of Labor Statistics","US","https://www.bls.gov/feed/empsit.rss","bls.gov"),
}
JOBS={"RELEASE_"+key:key for key in FIELDS}
NOTICE=("Official feed headlines and publisher timestamps only. Publication is not a quantified economic surprise or independently verified market impact. "
        "No upcoming event is treated as a completed release; no sentiment or directional forecast is inferred. "
        "Empty or stale feeds do not establish absence of risk. Coverage is limited to the enabled official sources.")
TOPICS={
    "MONETARY_POLICY":r"\b(?:monetary policy|FOMC|interest rate[s]?|policy rate[s]?|governing council)\b",
    "INFLATION":r"\b(?:inflation|consumer price[s]?|producer price[s]?|CPI|PPI)\b",
    "EMPLOYMENT":r"\b(?:employment situation|payroll[s]?|unemployment|labou?r market)\b",
    "FINANCIAL_STABILITY":r"\b(?:financial stability|liquidity|banking system)\b",
    "ECONOMIC_OUTLOOK":r"\b(?:economic outlook|economic projection[s]?|GDP|economic growth)\b",
}
DC="{http://purl.org/dc/elements/1.1/}"
RSS1="{http://purl.org/rss/1.0/}"
RDF="{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"

def permitted(key):
    return (key in FIELDS and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and key in {v.strip() for v in os.getenv("ATLAS_GLOBAL_RELEASES_SOURCES","").split(",")})

def _stamp(raw):
    if not isinstance(raw,str) or len(raw)>100:
        raise ValueError("RELEASE_TIMESTAMP_INVALID")
    try:
        stamp=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError:
        stamp=parsedate_to_datetime(raw)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("RELEASE_TIMESTAMP_INVALID")
    return stamp.astimezone(timezone.utc)

def _link(raw,key):
    if not isinstance(raw,str) or not 8<=len(raw)<=1000 or any(ch.isspace() or ord(ch)<32 for ch in raw):
        raise ValueError("RELEASE_LINK_INVALID")
    p=urlsplit(raw)
    host=FIELDS[key][4]
    if (p.scheme not in ("http","https") or p.hostname not in (host,"www."+host)
            or p.username is not None or p.password is not None or p.port not in (None,443)
            or p.query or not p.path.startswith("/") or p.path=="/" or "\\" in raw):
        raise ValueError("RELEASE_LINK_INVALID")
    # Upgrade only the known official HTTP link to its HTTPS equivalent.
    return urlunsplit(("https",p.hostname,p.path,"",""))

def _topics(key,title):
    fixed={"FED":"MONETARY_POLICY","BLS_CPI":"INFLATION","BLS_PPI":"INFLATION","BLS_JOBS":"EMPLOYMENT"}
    result={name for name,pattern in TOPICS.items() if re.search(pattern,title,re.I)}
    if key in fixed:
        result.add(fixed[key])
    return sorted(result)

def normalize(payload,key,instant):
    if len(payload)>MAX_BYTES:
        raise ValueError("RELEASE_BYTE_LIMIT")
    raw=payload.decode("utf-8-sig")
    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper() or "\x00" in raw:
        raise ValueError("UNSAFE_XML")
    root=ET.fromstring(raw)
    if root.tag=="rss":
        channel=root.find("channel")
        if channel is None:
            raise ValueError("RELEASE_SCHEMA_INVALID")
        items=channel.findall("item")
        ns=""
    elif root.tag==RDF+"RDF":
        if root.find(RSS1+"channel") is None:
            raise ValueError("RELEASE_SCHEMA_INVALID")
        items=root.findall(RSS1+"item")
        ns=RSS1
    else:
        raise ValueError("RELEASE_SCHEMA_INVALID")
    if len(items)>500:
        raise ValueError("RELEASE_ITEM_LIMIT")
    output={}
    valid=0
    for item in items:
        try:
            title=" ".join((item.findtext(ns+"title") or "").split())
            if not 8<=len(title)<=300 or "<" in title or ">" in title:
                raise ValueError("RELEASE_TITLE_INVALID")
            stamp=_stamp(item.findtext("pubDate") or item.findtext(DC+"date"))
            url=_link(item.findtext(ns+"link"),key)
            if stamp>instant:
                continue
            valid+=1
            if instant-stamp>timedelta(days=7):
                continue
            ident=sha256((url+"\n"+stamp.isoformat()).encode()).hexdigest()[:40]
            event={"id":ident,"headline":title,"source_name":FIELDS[key][1],"source_url":url,
                   "geography":FIELDS[key][2],"published_at":stamp.isoformat(),"topics":_topics(key,title),
                   "status":"PUBLISHED_FEED_HEADLINE","sentiment":"NOT_ANALYZED"}
            if ident in output and output[ident]!=event:
                raise ValueError("RELEASE_ID_CONFLICT")
            output[ident]=event
        except (TypeError,ValueError,OverflowError,AttributeError):
            continue
    if items and not valid:
        raise ValueError("RELEASE_NO_VALID_ITEMS")
    return sorted(output.values(),key=lambda x:(x["published_at"],x["id"]),reverse=True)[:50]

def collect(key,instant):
    return normalize(_download(FIELDS[key][3],{}),key,instant)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS global_release_snapshot(
        source TEXT PRIMARY KEY,captured_at TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,key,instant=None,loader=collect):
    if not permitted(key):
        return
    instant=instant or datetime.now(timezone.utc)
    rows=loader(key,instant)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO global_release_snapshot VALUES(?,?,?)
            ON CONFLICT(source) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
            WHERE excluded.captured_at>=global_release_snapshot.captured_at""",
            (key,instant.isoformat(),json.dumps(rows,allow_nan=False)))

def read(connect,instant=None):
    instant=instant or datetime.now(timezone.utc)
    sources=[]
    events={}
    conflicts=set()
    with closing(connect()) as db:
        _table(db)
        for key,(label,_,_,_,_) in FIELDS.items():
            status={"source":key,"label":label,"status":"DISABLED_OR_NOT_AUTHORIZED","event_count":0}
            sources.append(status)
            if not permitted(key):
                continue
            status["status"]="AWAITING_EVIDENCE"
            row=db.execute("SELECT captured_at,payload FROM global_release_snapshot WHERE source=?",(key,)).fetchone()
            if not row:
                continue
            stamp=_stamp(row["captured_at"])
            if not timedelta(0)<=instant-stamp<=timedelta(hours=2):
                status["status"]="STALE_CAPTURE"
                continue
            rows=[e for e in json.loads(row["payload"]) if timedelta(0)<=instant-_stamp(e["published_at"])<=timedelta(days=7)]
            status.update(status="CURRENT_FEED" if rows else "NO_RECENT_RETURNED_HEADLINES",
                          retrieved_at=stamp.isoformat(),event_count=len(rows))
            for e in rows:
                prev=events.get(e["id"])
                if prev is not None:
                    if any(prev[k]!=e[k] for k in ("headline","source_name","source_url","published_at","geography")):
                        conflicts.add(e["id"])
                        continue
                    prev["topics"]=sorted(set(prev["topics"])|set(e["topics"]))
                else:
                    events[e["id"]]=dict(e)
    current=sum(s["status"] in ("CURRENT_FEED","NO_RECENT_RETURNED_HEADLINES") for s in sources)
    return {"status":"AVAILABLE" if current==len(sources) else "PARTIAL" if current else "UNAVAILABLE",
            "sources":sources,"events":sorted((e for k,e in events.items() if k not in conflicts),
                key=lambda e:(e["published_at"],e["id"]),reverse=True)[:30],"notice":NOTICE}

def alerts(connect,instant=None):
    instant=instant or datetime.now(timezone.utc)
    return [{"id":"global-release-"+e["id"],"category":"MARKET_EVENT","title":e["headline"][:160],
             "description":"Official publisher headline; review topics: "+", ".join(e["topics"])+
                 ". Economic surprise and Indian market impact are not established.",
             "published_at":e["published_at"],"source_name":e["source_name"],"source_url":e["source_url"]}
            for e in read(connect,instant)["events"] if e["topics"]
            and timedelta(0)<=instant-_stamp(e["published_at"])<=timedelta(hours=72)]
