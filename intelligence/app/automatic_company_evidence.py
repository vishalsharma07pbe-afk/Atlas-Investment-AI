"""Bounded authorized company research, independent of portfolio identity.

Retrieval dates are not financial-period dates. Cached evidence never qualifies
a recommendation or establishes fair value.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from math import isfinite
from zoneinfo import ZoneInfo
import json
import os
import re

from .p1_research import company_research
from .financial_trends import summarize as financial_trends
from .fundamental_quality import summarize as fundamental_quality

ISIN = re.compile(r"^IN[A-Z0-9]{10}$")
HORIZONS = ("LONG_TERM", "SHORT_TERM", "SWING")
SECTIONS = ("profile","ratios","income_statement","balance_sheet","cash_flow","shareholding","corporate_actions","competitors")


def permitted():
    return (os.getenv("ATLAS_AUTOMATIC_COMPANY_RESEARCH_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED","false").lower()=="true"
            and bool(os.getenv("UPSTOX_ACCESS_TOKEN","").strip()))


def identify(snapshot):
    for section in snapshot["sections"]:
        if section["status"]!="READY" or section["section"] not in ("NSE","BSE"):
            continue
        for horizon in HORIZONS:
            for item in (section.get("result") or {}).get("horizons",{}).get(horizon,{}).get("candidates",[]):
                isin=item.get("isin")
                if isinstance(isin,str) and ISIN.fullmatch(isin) and item.get("exchange")==section["section"]:
                    yield item,isin


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_company_evidence(
        isin TEXT PRIMARY KEY, attempted_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL,
        status TEXT NOT NULL, payload TEXT)""")


def text(value):
    return value.strip()[:180] if isinstance(value,str) else None


def number(value):
    if isinstance(value,bool) or value is None:
        return None
    try:
        n=float(str(value).strip().rstrip("%"))
        return n if isfinite(n) else None
    except (TypeError,ValueError,OverflowError):
        return None


def history(rows, category="category"):
    result=[]
    for row in rows[:40] if isinstance(rows,list) else []:
        if not isinstance(row,dict) or not text(row.get(category)):
            continue
        points=[]
        raw=row.get("history")
        for point in raw[:5] if isinstance(raw,list) else []:
            if not isinstance(point,dict):
                continue
            period=text(point.get("period"))
            value=number(point.get("value"))
            if period and value is not None:
                points.append({"period":period,"value":value})
        if points:
            result.append({"name":text(row[category]),"history":points})
    return result


def normalize(report, isin, instant):
    if report.get("isin")!=isin or not isinstance(report.get("sections"),dict):
        raise ValueError("COMPANY_IDENTITY_MISMATCH")
    sections={}
    for key in SECTIONS:
        section=report["sections"].get(key) or {}
        raw=section.get("data") if section.get("status")=="AVAILABLE" else None
        data=None
        if key=="profile" and isinstance(raw,dict):
            data={k:text(raw.get(k)) for k in ("sector","industry","company_name") if text(raw.get(k))}
        elif key=="ratios" and isinstance(raw,list):
            data=[]
            for r in raw[:50]:
                if not isinstance(r,dict) or not text(r.get("name")):
                    continue
                company=number(r.get("company_value"))
                sector=number(r.get("sector_value"))
                if company is not None:
                    data.append({"name":text(r["name"]),"company_value":company,"sector_value":sector,
                                 "unit":r.get("unit") if r.get("unit") in ("PERCENT","RATIO") else "UNKNOWN",
                                 "sector_unit":r.get("sector_unit") if r.get("sector_unit") in ("PERCENT","RATIO") else "UNKNOWN"})
        elif key in ("income_statement","cash_flow") and isinstance(raw,dict):
            rows=history(raw.get(key))
            if rows:
                data={"units":text(raw.get("units_in")),"rows":rows,
                      "statement_type":text(raw.get("type")),"time_period":text(raw.get("time_period"))}
        elif key=="balance_sheet" and isinstance(raw,dict):
            rows=[]
            for point in raw.get("history",[])[:5] if isinstance(raw.get("history"),list) else []:
                if not isinstance(point,dict) or not text(point.get("period")):
                    continue
                values={k:number(point.get(k)) for k in ("total_asset","total_liability")}
                if any(v is not None for v in values.values()):
                    rows.append({"period":text(point["period"]),**values})
            if rows:
                data={"units":text(raw.get("units_in")),"rows":rows}
        elif key=="shareholding":
            data=history(raw)
        elif key in ("corporate_actions","competitors") and isinstance(raw,list):
            data=[]
            for row in raw[:12]:
                if not isinstance(row,dict):
                    continue
                name=text(row.get("name") or row.get("company_name"))
                if name:
                    data.append({"name":name,"date":text(row.get("expiry_date")),"sector":text(row.get("sector"))})
        source=section.get("source")
        endpoint=source.get("endpoint") if isinstance(source,dict) else None
        # Existing adapter supplies fixed public paths, never persist arbitrary URLs.
        if not isinstance(endpoint,str) or not re.fullmatch(r"/v2/fundamentals/[A-Z0-9%|._-]+/[a-z-]+",endpoint):
            endpoint=None
        sections[key]={"status":"AVAILABLE" if data else "UNAVAILABLE","data":data or None,
                       "source":{"provider":"UPSTOX","endpoint":endpoint,"retrieved_at":instant.isoformat()} if data else None}
    available=sum(s["status"]=="AVAILABLE" for s in sections.values())
    return {"isin":isin,"retrieved_at":instant.isoformat(),"sections":sections,
            "available_sections":available,"total_sections":len(SECTIONS),
            "notice":"Provider-reported evidence, not independently reconciled with filings. Ratio observation periods may be unspecified. Sector ratios are comparisons, not fair value."}


def refresh(snapshot, connect, loader=company_research, instant=None):
    if not snapshot["enabled"] or not permitted():
        return
    instant=instant or datetime.now(timezone.utc)
    stamp=instant.isoformat()
    candidates={}
    for item,isin in identify(snapshot):
        # Existing NSE ISIN key convention; BSE competitors require a mapping.
        if isin not in candidates or item["exchange"]=="NSE":
            candidates[isin]="NSE_EQ|"+isin if item["exchange"]=="NSE" else None
    if not candidates:
        return
    with closing(connect()) as db, db:
        _table(db)
        rows={r["isin"]:r for r in db.execute("SELECT isin,attempted_at,next_attempt_at,status FROM automatic_company_evidence")}
        # Avoid repeated requests across the universe when the provider rejects access.
        if any(r["status"]=="UNAVAILABLE" and r["attempted_at"]>(instant-timedelta(hours=1)).isoformat() for r in rows.values()):
            return
        due=sorted((isin for isin in candidates if isin not in rows or rows[isin]["next_attempt_at"]<=stamp),
                   key=lambda isin:(rows[isin]["attempted_at"] if isin in rows else "",isin))
        if not due:
            return
        isin=due[0]
        claim=db.execute("""INSERT INTO automatic_company_evidence VALUES(?,?,?,'RUNNING',NULL)
            ON CONFLICT(isin) DO UPDATE SET attempted_at=excluded.attempted_at,
            next_attempt_at=excluded.next_attempt_at,status='RUNNING',payload=NULL
            WHERE automatic_company_evidence.next_attempt_at<=?""",
            (isin,stamp,(instant+timedelta(hours=6)).isoformat(),stamp))
        if claim.rowcount!=1:
            return
    try:
        report=normalize(loader(isin,candidates[isin]),isin,instant)
        status="AVAILABLE" if report["available_sections"]==len(SECTIONS) else "PARTIAL" if report["available_sections"] else "UNAVAILABLE"
    except Exception:
        report=None
        status="UNAVAILABLE"
    with closing(connect()) as db, db:
        db.execute("""UPDATE automatic_company_evidence SET status=?,payload=?,next_attempt_at=?
            WHERE isin=? AND attempted_at=?""",
            (status,json.dumps(report,allow_nan=False) if report and status!="UNAVAILABLE" else None,
             (instant+timedelta(hours=24 if status=="AVAILABLE" else 6)).isoformat(),isin,stamp))
        db.execute("DELETE FROM automatic_company_evidence WHERE attempted_at<?",((instant-timedelta(days=30)).isoformat(),))


def attach(snapshot,connect,instant=None):
    snapshot["automatic_company_status"]="DISABLED_OR_NOT_AUTHORIZED"
    if not snapshot["enabled"] or not permitted():
        return snapshot
    snapshot["automatic_company_status"]="ENABLED"
    instant=instant or datetime.now(timezone.utc)
    with closing(connect()) as db:
        _table(db)
        rows={r["isin"]:r for r in db.execute("SELECT * FROM automatic_company_evidence WHERE status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?",
              ((instant-timedelta(hours=24)).isoformat(),instant.isoformat()))}
    for item,isin in identify(snapshot):
        row=rows.get(isin)
        if row and row["payload"]:
            report=json.loads(row["payload"])
            today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
            report["financial_trends"]=financial_trends(report,today.year,as_of=today)
            report["fundamental_quality"]=fundamental_quality(report,today.year)
            item["company_evidence"]=report
    return snapshot
