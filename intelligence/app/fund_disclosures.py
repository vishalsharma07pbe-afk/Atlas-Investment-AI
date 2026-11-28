"""Optional AMFI-derived disclosure snapshot from documented TigZig bulk API.

This is secondary reported evidence, not independently verified official filings.
Only public bulk data is requested; no owner holdings or identifiers leave ATLAS.
"""
from contextlib import closing
import csv
from datetime import date,datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
from collections import Counter
from decimal import Decimal,InvalidOperation
import gzip
import io
import json
import os
import re
import sqlite3
import time
from zoneinfo import ZoneInfo
import httpx
from . import nav_catalog

SOURCE="TIGZIG_AMFI_DERIVED"
URL="https://api.tigzig.com/mf/v1/download/scheme_details_latest.csv.gz"
INTERVAL=86400
MAX_COMPRESSED=16_000_000
MAX_RAW=64_000_000
MAX_ROWS=50000
IST=ZoneInfo("Asia/Kolkata")
REQUIRED={"source","scheme_code","isin","scheme_plan","category_sub",
          "amfi_daily_fund_aum_cr_all_plans","amfi_daily_aum_date","amfi_daily_aum_flag",
          "amfi_daily_riskometer","amfi_daily_benchmark","ssd_doc_date",
          "ssd_fund_managers","ssd_exit_load","ssd_benchmark_tier1_std","ssd_riskometer_level",
          "ter_date","ter_direct","ter_regular","ter_ber_direct","ter_ber_regular"}
RISK={"LOW","LOW_TO_MODERATE","MODERATE","MODERATELY_HIGH","HIGH","VERY_HIGH"}


def permitted():
    return (os.getenv("ATLAS_MF_DISCLOSURE_AUTO_REFRESH_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true")


def _text(value,limit=300):
    value=(value or "").strip()
    return value if value and len(value)<=limit and not any(ord(c)<32 and c not in "\n\t\r" for c in value) else None


def _day(value,today,age):
    try:
        if not isinstance(value,str) or not value:
            return None
        if len(value)==10:
            d=date.fromisoformat(value)
        else:
            d=datetime.fromisoformat(value.replace("Z","+00:00")).date()
        return d.isoformat() if 0<=(today-d).days<=age else None
    except ValueError:
        return None


def _number(value,maximum):
    try:
        d=Decimal(value)
        return float(d) if d.is_finite() and 0<=d<=maximum else None
    except (InvalidOperation,TypeError,ValueError):
        return None


def _risk(value):
    v=re.sub(r"[^A-Z]+","_",str(value or "").upper()).strip("_")
    return v if v in RISK else None


def parse(payload,today,*,audit=None):
    statuses={}
    if len(payload)>MAX_COMPRESSED:
        raise ValueError("DISCLOSURE_COMPRESSED_LIMIT")
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
        raw=stream.read(MAX_RAW+1)
    if len(raw)>MAX_RAW:
        raise ValueError("DISCLOSURE_DECOMPRESSED_LIMIT")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig"),newline=""))
    headers=reader.fieldnames or []
    if len(set(headers))!=len(headers) or not REQUIRED.issubset(headers):
        raise ValueError("DISCLOSURE_SCHEMA_CHANGED")
    result={}
    seen=set()
    for count,row in enumerate(reader,1):
        if count>MAX_ROWS:
            raise ValueError("DISCLOSURE_ROW_LIMIT")
        if None in row or any(v is None for v in row.values()):
            raise ValueError("DISCLOSURE_MALFORMED_ROW")
        if row["source"]!="MF":
            continue
        code=row["scheme_code"]
        if not re.fullmatch(r"[1-9][0-9]{5,8}",code or ""):
            continue
        if code in seen:
            raise ValueError("DISCLOSURE_DUPLICATE_SCHEME")
        seen.add(code)
        isin=row["isin"]
        plan=row["scheme_plan"].upper()
        if not re.fullmatch(r"INF[A-Z0-9]{9}",isin or "") or plan not in ("DIRECT","REGULAR"):
            statuses[code]="INVALID_IDENTITY_OR_PLAN"
            continue
        category=_text(row["category_sub"])
        if not category:
            statuses[code]="MISSING_CATEGORY"
            continue
        aum_date=_day(row["amfi_daily_aum_date"],today,14)
        ter_date=_day(row["ter_date"],today,90)
        doc_date=_day(row["ssd_doc_date"],today,365)
        benchmark=_text(row["amfi_daily_benchmark"]) if aum_date else None
        risk=_risk(row["amfi_daily_riskometer"]) if aum_date else None
        filed_benchmark=_text(row["ssd_benchmark_tier1_std"]) if doc_date else None
        filed_risk=_risk(row["ssd_riskometer_level"]) if doc_date else None
        conflicts=[]
        if benchmark and filed_benchmark and benchmark.casefold()!=filed_benchmark.casefold():
            conflicts.append("BENCHMARK_CONFLICT")
        if risk and filed_risk and risk!=filed_risk:
            conflicts.append("RISKOMETER_CONFLICT")
        if conflicts:
            benchmark=None if "BENCHMARK_CONFLICT" in conflicts else benchmark
            risk=None if "RISKOMETER_CONFLICT" in conflicts else risk
        key=plan.lower()
        fields={"scheme_code":code,"isin":isin,"plan":plan,"category":category,
                "fund_id":_text(row.get("amfi_ssd_fund_id"),80),
                "source":SOURCE,"source_url":URL,"status":"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
                "aum_date":aum_date,"aum_cr_all_plans":_number(row["amfi_daily_fund_aum_cr_all_plans"],Decimal("100000000")) if aum_date and not row["amfi_daily_aum_flag"].strip() else None,
                "benchmark":benchmark,"riskometer":risk,"ter_date":ter_date,
                "ter_percent":_number(row["ter_"+key],Decimal("100")) if ter_date else None,
                "base_expense_percent":_number(row["ter_ber_"+key],Decimal("100")) if ter_date else None,
                "document_date":doc_date,"fund_managers":_text(row["ssd_fund_managers"],1000) if doc_date else None,
                "exit_load":_text(row["ssd_exit_load"],2000) if doc_date else None,
                "conflicts":conflicts}
        if any(fields[k] is not None for k in ("aum_cr_all_plans","benchmark","riskometer","ter_percent","base_expense_percent","fund_managers","exit_load")):
            result[code]=fields
            statuses[code]="ACCEPTED"
        else:
            statuses[code]="NO_CURRENT_FIELDS"
    if audit is not None:
        audit.update(statuses)
    if not result:
        raise ValueError("NO_USABLE_DISCLOSURES")
    return result


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS fund_disclosure_snapshot(
        scheme_code TEXT PRIMARY KEY, payload TEXT NOT NULL, collected_at TEXT NOT NULL)""")


def store(payload,today,stamp):
    audit={}
    rows=parse(payload,today,audit=audit)
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _table(db)
        db.execute("DELETE FROM fund_disclosure_snapshot")
        db.executemany("INSERT INTO fund_disclosure_snapshot VALUES(?,?,?)",
                       [(code,json.dumps(row,allow_nan=False),stamp) for code,row in rows.items()])
        db.execute("""CREATE TABLE IF NOT EXISTS fund_disclosure_ingestion_audit(
          scheme_code TEXT PRIMARY KEY,status TEXT NOT NULL,collected_at TEXT NOT NULL)""")
        db.execute("DELETE FROM fund_disclosure_ingestion_audit")
        db.executemany("INSERT INTO fund_disclosure_ingestion_audit VALUES(?,?,?)",
                       [(code,status,stamp) for code,status in audit.items()])
    return len(rows)


def _cooldown_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS fund_bulk_source_cooldown(
      singleton INTEGER PRIMARY KEY CHECK(singleton=1),blocked_until REAL NOT NULL,reason TEXT NOT NULL)""")


def bulk_cooldown(instant=None):
    instant=instant or datetime.now(timezone.utc)
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _cooldown_table(db)
        row=db.execute("SELECT blocked_until,reason FROM fund_bulk_source_cooldown WHERE singleton=1").fetchone()
    if not row or row["blocked_until"]<=instant.timestamp():
        return None
    return {"blocked_until":datetime.fromtimestamp(row["blocked_until"],timezone.utc).isoformat(),
            "reason":row["reason"] if row["reason"] in ("RATE_LIMITED","ACCESS_REJECTED","SERVICE_UNAVAILABLE") else "SOURCE_COOLDOWN"}


def record_bulk_failure(error,instant=None):
    # Both secondary bulk files use the same publisher. Never evade its
    # backoff by rotating to the other file or restarting ATLAS.
    instant=instant or datetime.now(timezone.utc)
    if not isinstance(error,httpx.HTTPStatusError):
        return
    code=error.response.status_code
    reason={429:"RATE_LIMITED",401:"ACCESS_REJECTED",403:"ACCESS_REJECTED",503:"SERVICE_UNAVAILABLE"}.get(code)
    if not reason:
        return
    until=instant+timedelta(hours=6)
    value=error.response.headers.get("Retry-After","").strip()
    try:
        requested=instant+timedelta(seconds=int(value)) if re.fullmatch(r"[0-9]{1,12}",value) else parsedate_to_datetime(value)
        if requested.tzinfo is None:requested=requested.replace(tzinfo=timezone.utc)
        until=max(until,requested)
    except (ValueError,TypeError,OverflowError):pass
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _cooldown_table(db)
        db.execute("""INSERT INTO fund_bulk_source_cooldown VALUES(1,?,?)
          ON CONFLICT(singleton) DO UPDATE SET blocked_until=excluded.blocked_until,reason=excluded.reason
          WHERE excluded.blocked_until>=fund_bulk_source_cooldown.blocked_until""",(until.timestamp(),reason))


def refresh():
    if not permitted():
        raise ValueError("DISCLOSURE_SOURCE_NOT_AUTHORIZED")
    if bulk_cooldown():
        return 0
    deadline=time.monotonic()+90
    payload=bytearray()
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={"User-Agent":"ATLAS-Research/1.0","Accept-Encoding":"identity"}) as client:
            with client.stream("GET",URL) as response:
                response.raise_for_status()
                for part in response.iter_raw():
                    if time.monotonic()>deadline or len(payload)+len(part)>MAX_COMPRESSED:
                        raise ValueError("DISCLOSURE_DOWNLOAD_LIMIT")
                    payload.extend(part)
    except httpx.HTTPStatusError as error:
        record_bulk_failure(error)
        raise ValueError("DISCLOSURE_HTTP_FAILED") from None
    stamp=datetime.now(timezone.utc)
    return store(bytes(payload),stamp.astimezone(IST).date(),stamp.isoformat())


def ingestion_coverage(instant=None):
    """Aggregate source acceptance and field coverage, not official evidence."""
    if not permitted():
        return {"status":"DISABLED_OR_NOT_AUTHORIZED"}
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    try:
        cooldown=bulk_cooldown(instant)
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('fund_disclosure_snapshot','fund_disclosure_ingestion_audit')")}
            if "fund_disclosure_snapshot" not in tables:
                return {"status":"NO_SNAPSHOT","publisher_cooldown":cooldown}
            rows=db.execute("SELECT scheme_code,payload,collected_at FROM fund_disclosure_snapshot").fetchall()
            if not rows:
                return {"status":"NO_SNAPSHOT","publisher_cooldown":cooldown}
            stamps={r["collected_at"] for r in rows}
            if len(stamps)!=1:
                return {"status":"INCONSISTENT_SNAPSHOT","publisher_cooldown":cooldown}
            stamp=next(iter(stamps))
            counts=Counter()
            fields=Counter()
            for row in rows:
                try:
                    item=json.loads(row["payload"])
                    if item.get("scheme_code")!=row["scheme_code"] or item.get("source")!=SOURCE:
                        counts["INVALID_STORED_ROW"]+=1
                        continue
                    counts["VALID_STORED_ROW"]+=1
                    for day,age,names in (("aum_date",14,("aum_cr_all_plans","benchmark","riskometer")),
                                          ("ter_date",90,("ter_percent","base_expense_percent")),
                                          ("document_date",365,("fund_managers","exit_load"))):
                        if _day(item.get(day),today,age):
                            for name in names:
                                if item.get(name) is not None:fields[name]+=1
                except (ValueError,TypeError,AttributeError,KeyError):
                    counts["INVALID_STORED_ROW"]+=1
            audit={}
            if "fund_disclosure_ingestion_audit" in tables:
                seen=db.execute("SELECT scheme_code,status,collected_at FROM fund_disclosure_ingestion_audit").fetchall()
                allowed={"ACCEPTED","INVALID_IDENTITY_OR_PLAN","MISSING_CATEGORY","NO_CURRENT_FIELDS"}
                if seen and all(a["collected_at"]==stamp and a["status"] in allowed for a in seen) and {a["scheme_code"] for a in seen if a["status"]=="ACCEPTED"}=={row["scheme_code"] for row in rows}:
                    audit=dict(Counter(a["status"] for a in seen))
        fresh=bool(_day(stamp,today,2))
        return {"status":"LAST_SUCCESSFUL_SECONDARY_FILE" if fresh else "STALE_SECONDARY_FILE",
                "collected_at":stamp,"stored_scheme_count":len(rows),"stored_counts":dict(counts),
                "source_counts":audit,"fresh_field_counts":dict(fields) if fresh else {},
                "publisher_cooldown":cooldown,
                "notice":"Secondary source acceptance only; fresh field counts use original dates, not download date. Empty source counts mean ingestion audit unavailable."}
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return {"status":"ACQUISITION_AUDIT_UNAVAILABLE"}


def matched(rows,today,*,limit=5):
    # Preserve the existing display cap by default; internal research may
    # explicitly request the entire bounded category sample.
    if type(limit) is not int or not 1<=limit<=40:
        raise ValueError("INVALID_DISCLOSURE_MATCH_LIMIT")
    if not permitted() or not rows:
        return []
    output=[]
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for row in rows[:40]:
                if len(output)>=limit:break
                code=row.get("scheme_code")
                if type(code) is not int:
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_disclosure_snapshot WHERE scheme_code=?",(str(code),)).fetchone()
                if not found:
                    continue
                try:
                    item=json.loads(found["payload"])
                    if (_day(found["collected_at"],today,2) is None or item["scheme_code"]!=str(code)
                        or item.get("source")!=SOURCE or item["isin"]!=row.get("isin_growth")
                        or item["plan"]!=row.get("amfi_plan") or row.get("amfi_option")!="GROWTH"
                        or not isinstance(row.get("category"),str)
                        or not row["category"].lower().strip().endswith(" - "+item["category"].lower()+")")):
                        continue
                    for field,age_limit,values in (("aum_date",14,("aum_cr_all_plans","benchmark","riskometer")),
                                               ("ter_date",90,("ter_percent","base_expense_percent")),
                                               ("document_date",365,("fund_managers","exit_load"))):
                        if not _day(item[field],today,age_limit):
                            for value in values:
                                item[value]=None
                            item[field]=None
                    output.append({**item,"scheme_name":row["scheme_name"],"collected_at":found["collected_at"]})
                except (ValueError,TypeError,KeyError,AttributeError):
                    continue
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError):
        return []
    return output
