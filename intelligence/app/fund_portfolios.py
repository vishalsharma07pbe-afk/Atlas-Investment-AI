"""Bounded secondary AMC portfolio observations, never a verified growth forecast."""
import csv
import io
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from contextlib import closing
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
import httpx
from . import nav_catalog,fund_disclosures

URL="https://api.tigzig.com/downloads/mf_portfolio_holdings.csv"
INTERVAL=86400
MAX_BYTES=16_000_000
MAX_ROWS=100000
IST=ZoneInfo("Asia/Kolkata")
REQUIRED={"fund_code","fund_name","month_end","isin","isin_as_filed","security_name",
          "pct_of_fund","asset_group","asset_subgroup","mapping_category","amfi_ssd_fund_id","isin_type"}
GROUPS={"Equity","Foreign stocks","Cash","Money market","Mutual fund units","REITs and InvITs","Debt","Others"}
ISIN=re.compile(r"INE[A-Z0-9]{9}")


def permitted():
    return fund_disclosures.permitted()


def parse(payload,today):
    if len(payload)>MAX_BYTES:
        raise ValueError("PORTFOLIO_BYTE_LIMIT")
    reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig"),newline=""))
    headers=reader.fieldnames or []
    if len(set(headers))!=len(headers) or not REQUIRED.issubset(headers):
        raise ValueError("PORTFOLIO_SCHEMA_CHANGED")
    groups=defaultdict(list)
    latest={}
    fund_codes=defaultdict(set)
    for n,row in enumerate(reader,1):
        if n>MAX_ROWS:
            raise ValueError("PORTFOLIO_ROW_LIMIT")
        if None in row or any(v is None for v in row.values()):
            raise ValueError("PORTFOLIO_MALFORMED_ROW")
        fund=row["amfi_ssd_fund_id"].strip()
        if not fund or len(fund)>80:
            continue
        day=date.fromisoformat(row["month_end"])
        if day>today:
            raise ValueError("PORTFOLIO_FUTURE_DATE")
        if (today-day).days>60:
            continue
        latest[fund]=max(latest.get(fund,day),day)
        key=(fund,day)
        fund_codes[key].add(row["fund_code"])
        groups[key].append(row)
    output={}
    for fund,day in latest.items():
        rows=groups[(fund,day)]
        if len(fund_codes[(fund,day)])!=1 or not 1<=len(rows)<=1000:
            continue
        allocations=defaultdict(Decimal)
        equities=defaultdict(Decimal)
        names={}
        seen=set()
        valid=True
        for row in rows:
            fingerprint=tuple(row[k] for k in sorted(REQUIRED))
            try:
                weight=Decimal(row["pct_of_fund"])
            except InvalidOperation:
                valid=False;break
            group=row["asset_group"]
            if (fingerprint in seen or group not in GROUPS or not weight.is_finite()
                or abs(weight)>100 or (weight<0 and group!="Others")):
                valid=False;break
            seen.add(fingerprint)
            allocations[group]+=weight
            isin=row["isin"]
            if (group=="Equity" and row["asset_subgroup"]=="Listed shares" and row["isin_type"]=="ISIN"
                and ISIN.fullmatch(isin) and row["isin_as_filed"]==isin and not row["mapping_category"] and weight>0):
                equities[isin]+=weight
                names[isin]=row["security_name"][:200]
        total=sum(allocations.values(),Decimal(0))
        if not valid or not Decimal("99.5")<=total<=Decimal("100.5") or sum(equities.values())>Decimal("100.5"):
            continue
        ordered=sorted(equities,key=lambda k:(-equities[k],k))
        output[fund]={"fund_id":fund,"portfolio_date":day.isoformat(),"source":"TIGZIG_AMC_DERIVED",
            "source_url":URL,"reported_weight_total_percent":float(total),
            "asset_allocation_percent":{k:float(v) for k,v in sorted(allocations.items())},
            "exact_listed_equity_weight_percent":float(sum(equities.values())),
            "top_10_exact_equity_weight_percent":float(sum(equities[k] for k in ordered[:10])),
            "exact_equity_count":len(ordered),
            "equities":[{"isin":k,"name":names[k],"weight_percent":float(equities[k])} for k in ordered],
            "notice":"Secondary reported portfolio. Weight total is a reconciliation check, not proof of completeness. Derivative exposures outside reported net assets may be missing."}
    if not output:
        raise ValueError("NO_USABLE_PORTFOLIOS")
    return output


def store(payload,today,stamp):
    rows=parse(payload,today)
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        db.execute("""CREATE TABLE IF NOT EXISTS fund_portfolio_snapshot(
            fund_id TEXT PRIMARY KEY,payload TEXT NOT NULL,collected_at TEXT NOT NULL)""")
        db.execute("DELETE FROM fund_portfolio_snapshot")
        db.executemany("INSERT INTO fund_portfolio_snapshot VALUES(?,?,?)",
                       [(k,json.dumps(v,allow_nan=False),stamp) for k,v in rows.items()])
    return len(rows)


def refresh():
    if not permitted():
        raise ValueError("PORTFOLIO_SOURCE_NOT_AUTHORIZED")
    deadline=time.monotonic()+90
    payload=bytearray()
    with httpx.Client(timeout=20,follow_redirects=False,headers={"User-Agent":"ATLAS-Research/1.0","Accept-Encoding":"identity"}) as client:
        with client.stream("GET",URL) as response:
            response.raise_for_status()
            for part in response.iter_bytes():
                if time.monotonic()>deadline or len(payload)+len(part)>MAX_BYTES:
                    raise ValueError("PORTFOLIO_DOWNLOAD_LIMIT")
                payload.extend(part)
    stamp=datetime.now(timezone.utc)
    return store(bytes(payload),stamp.astimezone(IST).date(),stamp.isoformat())


def company_coverage(equities,instant):
    # Existing public company cache only; no extra external calls or name guesses.
    from .automatic_company_evidence import permitted as company_permitted
    if not company_permitted() or not equities:
        return {"cached_company_evidence_weight_percent":0,"cached_company_count":0}
    path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3"))
    found=set()
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=2)) as db:
            for holding in equities:
                row=db.execute("""SELECT payload FROM automatic_company_evidence WHERE isin=?
                    AND status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?""",
                    (holding["isin"],(instant-timedelta(hours=24)).isoformat(),instant.isoformat())).fetchone()
                if row and row[0]:
                    item=json.loads(row[0])
                    if item.get("isin")==holding["isin"] and item.get("available_sections",0)>0:
                        found.add(holding["isin"])
    except (OSError,sqlite3.Error,ValueError,TypeError,AttributeError):
        found.clear()
    return {"cached_company_evidence_weight_percent":round(sum(h["weight_percent"] for h in equities if h["isin"] in found),4),
            "cached_company_count":len(found)}


def matched(disclosures,instant=None):
    if not permitted() or not disclosures:
        return []
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    result=[]
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for item in disclosures[:5]:
                fund=item.get("fund_id")
                if not fund:
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_portfolio_snapshot WHERE fund_id=?",(fund,)).fetchone()
                if not found or not fund_disclosures._day(found["collected_at"],today,2):
                    continue
                report=json.loads(found["payload"])
                if report.get("fund_id")!=fund or not fund_disclosures._day(report["portfolio_date"],today,60):
                    continue
                equities=report.pop("equities")
                result.append({**report,**company_coverage(equities,instant),
                    "scheme_code":item["scheme_code"],"scheme_name":item["scheme_name"],
                    "collected_at":found["collected_at"],"top_holdings":equities[:10],
                    "status":"SECONDARY_COMPOSITION_ONLY"})
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError):
        return []
    return result


def overlap(disclosures,instant=None):
    """Compare full exact listed-equity weights on a shared disclosure date.
    Sum of per-ISIN minimum weights is a lower bound on reported common exposure,
    not normalized equity-only overlap or complete portfolio overlap.
    """
    if not permitted() or not disclosures:
        return {"status":"NOT_AVAILABLE_OR_NOT_AUTHORIZED","pairs":[]}
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    portfolios={}
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for item in disclosures[:5]:
                fund=item.get("fund_id")
                if not fund or fund in portfolios:
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_portfolio_snapshot WHERE fund_id=?",(fund,)).fetchone()
                if not found or not fund_disclosures._day(found["collected_at"],today,2):
                    continue
                report=json.loads(found["payload"])
                if report.get("fund_id")!=fund or not fund_disclosures._day(report["portfolio_date"],today,60):
                    continue
                weights={}
                for equity in report["equities"]:
                    key=equity["isin"]
                    value=Decimal(str(equity["weight_percent"]))
                    if not ISIN.fullmatch(key) or key in weights or not value.is_finite() or not 0<value<=100:
                        raise ValueError("INVALID_EQUITY_WEIGHT")
                    weights[key]=value
                coverage=sum(weights.values(),Decimal(0))
                if not Decimal("80")<=coverage<=Decimal("100.5"):
                    continue
                portfolios[fund]=(item,report["portfolio_date"],weights,coverage)
        pairs=[]
        values=list(portfolios.values())
        for i,(a,day,aw,ac) in enumerate(values):
            for b,bday,bw,bc in values[i+1:]:
                if day!=bday:
                    continue
                common=sorted(aw.keys()&bw.keys(),key=lambda k:(-min(aw[k],bw[k]),k))
                total=sum((min(aw[k],bw[k]) for k in common),Decimal(0))
                pairs.append({"scheme_a":a["scheme_code"],"name_a":a["scheme_name"],
                              "scheme_b":b["scheme_code"],"name_b":b["scheme_name"],
                              "portfolio_date":day,"common_equity_count":len(common),
                              "common_weight_lower_bound_percent":float(round(total,4)),
                              "exact_weight_a_percent":float(round(ac,4)),
                              "exact_weight_b_percent":float(round(bc,4)),
                              "largest_shared_equities":[{"isin":k,"weight_a_percent":float(aw[k]),
                                  "weight_b_percent":float(bw[k])} for k in common[:5]]})
        return {"status":"REPORTED_LOWER_BOUND" if pairs else "INSUFFICIENT_COMPARABLE_PORTFOLIOS",
                "pairs":pairs,"notice":"Same-date distinct funds with at least 80% exact listed equity coverage. Sum of minimum common weights in original fund NAV percentages; excludes unmapped, foreign, cash, debt and other exposures. Zero does not prove no overlap."}
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError,InvalidOperation):
        return {"status":"INSUFFICIENT_COMPARABLE_PORTFOLIOS","pairs":[]}
