"""Optional AMFI-derived disclosure snapshot from documented TigZig bulk API.

This is secondary reported evidence, not independently verified official filings.
Only public bulk data is requested; no owner holdings or identifiers leave ATLAS.
"""
from contextlib import closing
import csv
from datetime import date,datetime,timezone
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


def parse(payload,today):
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
        if not re.fullmatch(r"IN[A-Z0-9]{10}",isin or "") or plan not in ("DIRECT","REGULAR"):
            continue
        category=_text(row["category_sub"])
        if not category:
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
    if not result:
        raise ValueError("NO_USABLE_DISCLOSURES")
    return result


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS fund_disclosure_snapshot(
        scheme_code TEXT PRIMARY KEY, payload TEXT NOT NULL, collected_at TEXT NOT NULL)""")


def store(payload,today,stamp):
    rows=parse(payload,today)
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        _table(db)
        db.execute("DELETE FROM fund_disclosure_snapshot")
        db.executemany("INSERT INTO fund_disclosure_snapshot VALUES(?,?,?)",
                       [(code,json.dumps(row,allow_nan=False),stamp) for code,row in rows.items()])
    return len(rows)


def refresh():
    if not permitted():
        raise ValueError("DISCLOSURE_SOURCE_NOT_AUTHORIZED")
    deadline=time.monotonic()+90
    payload=bytearray()
    with httpx.Client(timeout=20,follow_redirects=False,headers={"User-Agent":"ATLAS-Research/1.0","Accept-Encoding":"identity"}) as client:
        with client.stream("GET",URL) as response:
            response.raise_for_status()
            for part in response.iter_raw():
                if time.monotonic()>deadline or len(payload)+len(part)>MAX_COMPRESSED:
                    raise ValueError("DISCLOSURE_DOWNLOAD_LIMIT")
                payload.extend(part)
    stamp=datetime.now(timezone.utc)
    return store(bytes(payload),stamp.astimezone(IST).date(),stamp.isoformat())


def matched(rows,today):
    if not permitted() or not rows:
        return []
    output=[]
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for row in rows[:5]:
                code=row.get("scheme_code")
                if type(code) is not int:
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_disclosure_snapshot WHERE scheme_code=?",(str(code),)).fetchone()
                if not found:
                    continue
                item=json.loads(found["payload"])
                if (_day(found["collected_at"],today,2) is None or item["isin"]!=row.get("isin_growth")
                    or item["plan"]!=row.get("amfi_plan") or row.get("amfi_option")!="GROWTH"
                    or not isinstance(row.get("category"),str)
                    or not row["category"].lower().strip().endswith(" - "+item["category"].lower()+")")):
                    continue
                for field,limit,values in (("aum_date",14,("aum_cr_all_plans","benchmark","riskometer")),
                                           ("ter_date",90,("ter_percent","base_expense_percent")),
                                           ("document_date",365,("fund_managers","exit_load"))):
                    if not _day(item[field],today,limit):
                        for value in values:
                            item[value]=None
                        item[field]=None
                output.append({**item,"scheme_name":row["scheme_name"],"collected_at":found["collected_at"]})
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError):
        return []
    return output
