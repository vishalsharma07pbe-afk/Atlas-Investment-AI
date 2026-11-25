"""Authorized normalized local public deal reports; no network acquisition."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import io
import json
import os
import re
import stat

IST=ZoneInfo("Asia/Kolkata")
PATH=Path("/app/deal-reports/deals.csv")
MAX_BYTES=2_000_000
FIELDS={"trade_date","exchange","symbol","isin","deal_type","client_name","side","quantity","price_inr","source_report"}
NOTICE=("Authorized local supplied report, not independently verified. Exact venue, symbol and ISIN as supplied; "
        "current watch match does not prove historical mapping. Bulk and block are separate disclosed sides, "
        "not additive market turnover, institutional classification or holdings. No rows do not prove no deals. "
        "Reported values are quantity times reported price, not settlement value. No forecast or trade signal.")


def permitted():
    return (os.getenv("ATLAS_DEAL_REPORTS_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true")


def _text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(ch)<32 for ch in value):
        raise ValueError("INVALID_REPORT_TEXT")
    return value.strip()


def parse(payload,today):
    if len(payload)>MAX_BYTES:
        raise ValueError("DEAL_BYTE_LIMIT")
    reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig"),newline=""))
    if reader.fieldnames is None or len(reader.fieldnames)!=len(FIELDS) or set(reader.fieldnames)!=FIELDS:
        raise ValueError("DEAL_SCHEMA_INVALID")
    rows=[]
    seen=set()
    for n,row in enumerate(reader,1):
        if n>10000 or None in row or any(v is None for v in row.values()):
            raise ValueError("DEAL_ROW_LIMIT_OR_SHAPE")
        day=date.fromisoformat(row["trade_date"])
        if not today-timedelta(days=120)<=day<=today:
            raise ValueError("DEAL_DATE_OUTSIDE_WINDOW")
        exchange,symbol,isin,kind,side=(row[k] for k in ("exchange","symbol","isin","deal_type","side"))
        if (exchange not in ("NSE","BSE") or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",symbol)
                or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or kind not in ("BULK","BLOCK") or side not in ("BUY","SELL")):
            raise ValueError("DEAL_IDENTITY_INVALID")
        client=_text(row["client_name"],180)
        reference=_text(row["source_report"],180)
        if not re.fullmatch(r"[0-9]{1,12}",row["quantity"]) or not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,4})?",row["price_inr"]):
            raise ValueError("DEAL_NUMERIC_INVALID")
        quantity=int(row["quantity"])
        price=Decimal(row["price_inr"])
        if quantity<=0 or price<=0:
            raise ValueError("DEAL_NUMERIC_INVALID")
        key=(day,exchange,symbol,isin,kind,client.casefold(),side,quantity,price)
        # No reliable transaction ID: identical sides cannot be safely counted twice.
        if key in seen:
            raise ValueError("DUPLICATE_DEAL_SIDE")
        seen.add(key)
        rows.append({"trade_date":day.isoformat(),"exchange":exchange,"symbol":symbol,"isin":isin,
                     "deal_type":kind,"client_name":client,"side":side,"quantity":str(quantity),
                     "price_inr":format(price,"f"),"source_report":reference})
    if not rows:
        raise ValueError("NO_REPORT_ROWS")
    return sorted(rows,key=lambda r:(r["trade_date"],r["exchange"],r["symbol"],r["deal_type"],r["client_name"],r["side"],r["quantity"],r["price_inr"]),reverse=True)


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS local_deal_reports(
        id INTEGER PRIMARY KEY CHECK(id=1), captured_at TEXT NOT NULL, payload TEXT NOT NULL)""")


def refresh(connect,instant=None,path=PATH):
    if not permitted():
        return False
    instant=instant or datetime.now(timezone.utc)
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:
        return False
    with os.fdopen(fd,"rb") as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_BYTES:
            raise ValueError("DEAL_FILE_INVALID")
        payload=stream.read(MAX_BYTES+1)
        after=os.fstat(stream.fileno())
        if before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size or len(payload)!=after.st_size:
            raise ValueError("DEAL_FILE_CHANGED")
    rows=parse(payload,instant.astimezone(IST).date())
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO local_deal_reports VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
            WHERE excluded.captured_at>=local_deal_reports.captured_at""",
            (instant.isoformat(),json.dumps(rows,ensure_ascii=True)))
    return True


def _summarize(rows):
    groups=[]
    for kind in ("BULK","BLOCK"):
        selected=[r for r in rows if r["deal_type"]==kind]
        if not selected:
            continue
        item={"deal_type":kind,"record_count":len(selected)}
        for side in ("BUY","SELL"):
            matched=[r for r in selected if r["side"]==side]
            item[side.lower()+"_quantity"]=str(sum(int(r["quantity"]) for r in matched))
            item[side.lower()+"_reported_value_inr"]=format(sum((Decimal(r["quantity"])*Decimal(r["price_inr"]) for r in matched),Decimal(0)),"f")
        groups.append(item)
    return {"status":"LOCAL_REPORTED_ONLY","latest_date":rows[0]["trade_date"],"groups":groups,
            "recent_records":rows[:10],"notice":NOTICE}


def attach(snapshot,connect,instant=None):
    summary={"status":"DISABLED_OR_NOT_AUTHORIZED","notice":NOTICE}
    snapshot.setdefault("institutional_activity",{})["deal_reports"]=summary
    if not snapshot.get("enabled") or not permitted():
        return snapshot
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    summary["status"]="NO_CURRENT_REPORT"
    with closing(connect()) as db:
        _table(db)
        row=db.execute("SELECT captured_at,payload FROM local_deal_reports WHERE id=1").fetchone()
    if not row:
        return snapshot
    stamp=datetime.fromisoformat(row["captured_at"])
    if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=48):
        return snapshot
    rows=[r for r in json.loads(row["payload"]) if 0<=(today-date.fromisoformat(r["trade_date"])).days<=30]
    if not rows:
        return snapshot
    summary.update(status="LOCAL_REPORTED_ONLY",record_count=len(rows),latest_date=rows[0]["trade_date"])
    indexed={}
    for r in rows:
        indexed.setdefault((r["exchange"],r["symbol"],r["isin"]),[]).append(r)
    from .automatic_company_evidence import identify
    items=list(identify(snapshot))
    for section in snapshot.get("sections",[]):
        if section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):
            continue
        review=(section.get("result") or {}).get("price_volume_review") or {}
        for key in ("downside_items","upside_items"):
            for item in review.get(key,[]):
                if item.get("exchange")==section["section"]:
                    items.append((item,item.get("isin")))
    for item,isin in items:
        found=indexed.get((item["exchange"],item.get("symbol"),isin))
        if found:
            item["deal_evidence"]=_summarize(found)
            # Compare only same observed date, never a rolling total to a daily bar.
            dated=[r for r in found if r["trade_date"]==item.get("as_of")]
            pressure=item.get("price_volume_pressure") or {}
            if dated and pressure.get("status")=="OBSERVED_PRICE_VOLUME_ONLY" and pressure.get("as_of")==item.get("as_of"):
                item["deal_evidence"]["same_date_groups"]=_summarize(dated)["groups"]
                item["deal_evidence"]["same_date_notice"]="Coincident supplied deal sides, not a causal or institutional attribution."
    return snapshot
