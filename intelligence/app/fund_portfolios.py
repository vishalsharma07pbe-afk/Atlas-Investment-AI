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
from .fund_categories import LABELS, DEBT, COMPARABLE

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


def parse(payload,today,*,audit=None):
    if len(payload)>MAX_BYTES:
        raise ValueError("PORTFOLIO_BYTE_LIMIT")
    reader=csv.DictReader(io.StringIO(payload.decode("utf-8-sig"),newline=""))
    headers=reader.fieldnames or []
    if len(set(headers))!=len(headers) or not REQUIRED.issubset(headers):
        raise ValueError("PORTFOLIO_SCHEMA_CHANGED")
    groups=defaultdict(list)
    latest={}
    fund_codes=defaultdict(set)
    statuses={}
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
            statuses.setdefault(fund,"STALE_PORTFOLIO_DATE")
            continue
        latest[fund]=max(latest.get(fund,day),day)
        key=(fund,day)
        fund_codes[key].add(row["fund_code"])
        groups[key].append(row)
    output={}
    for fund,day in latest.items():
        rows=groups[(fund,day)]
        if len(fund_codes[(fund,day)])!=1:
            statuses[fund]="CONFLICTING_FUND_CODES"
            continue
        if not 1<=len(rows)<=1000:
            statuses[fund]="HOLDING_COUNT_LIMIT"
            continue
        allocations=defaultdict(Decimal)
        equities=defaultdict(Decimal)
        names={}
        seen=set()
        reason=None
        for row in rows:
            fingerprint=tuple(row[k] for k in sorted(REQUIRED))
            try:
                weight=Decimal(row["pct_of_fund"])
            except InvalidOperation:
                reason="INVALID_WEIGHT";break
            group=row["asset_group"]
            if fingerprint in seen:
                reason="DUPLICATE_HOLDING_ROW";break
            if group not in GROUPS:
                reason="UNSUPPORTED_ASSET_GROUP";break
            if not weight.is_finite() or abs(weight)>100 or (weight<0 and group!="Others"):
                reason="INVALID_WEIGHT";break
            seen.add(fingerprint)
            allocations[group]+=weight
            isin=row["isin"]
            if (group=="Equity" and row["asset_subgroup"]=="Listed shares" and row["isin_type"]=="ISIN"
                and ISIN.fullmatch(isin) and row["isin_as_filed"]==isin and not row["mapping_category"] and weight>0):
                equities[isin]+=weight
                names[isin]=row["security_name"][:200]
        total=sum(allocations.values(),Decimal(0))
        if reason or not Decimal("99.5")<=total<=Decimal("100.5") or sum(equities.values())>Decimal("100.5"):
            statuses[fund]=reason or "WEIGHTS_NOT_RECONCILED"
            continue
        statuses[fund]="ACCEPTED"
        ordered=sorted(equities,key=lambda k:(-equities[k],k))
        output[fund]={"fund_id":fund,"portfolio_date":day.isoformat(),"source":"TIGZIG_AMC_DERIVED",
            "source_url":URL,"reported_weight_total_percent":float(total),
            "asset_allocation_percent":{k:float(v) for k,v in sorted(allocations.items())},
            "exact_listed_equity_weight_percent":float(sum(equities.values())),
            "top_10_exact_equity_weight_percent":float(sum(equities[k] for k in ordered[:10])),
            "exact_equity_count":len(ordered),
            "equities":[{"isin":k,"name":names[k],"weight_percent":float(equities[k])} for k in ordered],
            "notice":"Secondary reported portfolio. Weight total is a reconciliation check, not proof of completeness. Derivative exposures outside reported net assets may be missing."}
    if audit is not None:
        audit.update(statuses)
    if not output:
        raise ValueError("NO_USABLE_PORTFOLIOS")
    return output


def store(payload,today,stamp):
    audit={}
    rows=parse(payload,today,audit=audit)
    with nav_catalog._LOCK,closing(nav_catalog._connect()) as db,db:
        db.execute("""CREATE TABLE IF NOT EXISTS fund_portfolio_snapshot(
            fund_id TEXT PRIMARY KEY,payload TEXT NOT NULL,collected_at TEXT NOT NULL)""")
        db.execute("DELETE FROM fund_portfolio_snapshot")
        db.executemany("INSERT INTO fund_portfolio_snapshot VALUES(?,?,?)",
                       [(k,json.dumps(v,allow_nan=False),stamp) for k,v in rows.items()])
        db.execute("""CREATE TABLE IF NOT EXISTS fund_portfolio_ingestion_audit(
            fund_id TEXT PRIMARY KEY,status TEXT NOT NULL,collected_at TEXT NOT NULL)""")
        db.execute("DELETE FROM fund_portfolio_ingestion_audit")
        db.executemany("INSERT INTO fund_portfolio_ingestion_audit VALUES(?,?,?)",
                       [(k,v,stamp) for k,v in audit.items()])
    return len(rows)


def refresh():
    if not permitted():
        raise ValueError("PORTFOLIO_SOURCE_NOT_AUTHORIZED")
    if fund_disclosures.bulk_cooldown():
        return 0
    deadline=time.monotonic()+90
    payload=bytearray()
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={"User-Agent":"ATLAS-Research/1.0","Accept-Encoding":"identity"}) as client:
            with client.stream("GET",URL) as response:
                response.raise_for_status()
                for part in response.iter_bytes():
                    if time.monotonic()>deadline or len(payload)+len(part)>MAX_BYTES:
                        raise ValueError("PORTFOLIO_DOWNLOAD_LIMIT")
                    payload.extend(part)
    except httpx.HTTPStatusError as error:
        fund_disclosures.record_bulk_failure(error)
        raise ValueError("PORTFOLIO_HTTP_FAILED") from None
    stamp=datetime.now(timezone.utc)
    return store(bytes(payload),stamp.astimezone(IST).date(),stamp.isoformat())


def ingestion_coverage(disclosures=(),instant=None):
    """Read-only aggregate audit of the last successfully stored bulk file.
    Does not fetch, expose holding identities, or imply official coverage.
    """
    if not permitted():
        return {"status":"DISABLED_OR_NOT_AUTHORIZED","source_counts":{},"sample_counts":{}}
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    from collections import Counter
    sample=Counter()
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            rows=db.execute("SELECT fund_id,status,collected_at FROM fund_portfolio_ingestion_audit").fetchall()
            if not rows:
                return {"status":"NO_AUDIT","source_counts":{},"sample_counts":{}}
            stamps={row["collected_at"] for row in rows}
            if len(stamps)!=1 or not fund_disclosures._day(next(iter(stamps)),today,2):
                return {"status":"STALE_OR_INCONSISTENT_AUDIT","source_counts":{},"sample_counts":{}}
            allowed={"ACCEPTED","STALE_PORTFOLIO_DATE","CONFLICTING_FUND_CODES","HOLDING_COUNT_LIMIT",
                     "INVALID_WEIGHT","DUPLICATE_HOLDING_ROW","UNSUPPORTED_ASSET_GROUP","WEIGHTS_NOT_RECONCILED"}
            indexed={row["fund_id"]:row["status"] for row in rows}
            if not set(indexed.values())<=allowed:
                return {"status":"INVALID_AUDIT","source_counts":{},"sample_counts":{}}
            stored={row["fund_id"] for row in db.execute("SELECT fund_id FROM fund_portfolio_snapshot WHERE collected_at=?",(next(iter(stamps)),))}
            if stored!={k for k,v in indexed.items() if v=="ACCEPTED"}:
                return {"status":"INVALID_AUDIT","source_counts":{},"sample_counts":{}}
            for item in disclosures[:40]:
                fund=item.get("fund_id") if isinstance(item,dict) else None
                if not isinstance(fund,str) or not 0<len(fund)<=80:
                    sample["MISSING_FUND_ID"]+=1
                else:
                    sample[indexed.get(fund,"NOT_IN_SOURCE_FILE")]+=1
            return {"status":"LAST_SUCCESSFUL_SECONDARY_FILE","collected_at":next(iter(stamps)),
                    "source_counts":dict(sorted(Counter(indexed.values()).items())),
                    "sample_counts":dict(sorted(sample.items())),
                    "notice":"Source counts are distinct provider fund IDs, sample counts are matched disclosure scheme rows. Accepted means parser checks passed, not independently verified holdings."}
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError):
        return {"status":"NO_AUDIT_OR_STORAGE_UNAVAILABLE","source_counts":{},"sample_counts":{}}


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


def concentration(equities,sector_evidence,category,allocations):
    """Descriptive concentration of the identifiable subset, never full-fund risk."""
    label=category.strip().casefold() if isinstance(category,str) else ""
    kind=next((k for k,v in LABELS.items() if v==label),"UNKNOWN")
    if kind in DEBT:
        gaps=["ISSUER_AND_CREDIT_RATING_COVERAGE_REQUIRED","MATURITY_AND_MODIFIED_DURATION_REQUIRED",
              "CREDIT_SPREAD_AND_LIQUIDITY_EVIDENCE_REQUIRED"]
    elif kind=="AGGRESSIVE_HYBRID":
        gaps=["EQUITY_DEBT_ALLOCATION_RECONCILIATION_REQUIRED","DEBT_CREDIT_AND_DURATION_REQUIRED",
              "DERIVATIVE_AND_LIQUIDITY_EVIDENCE_REQUIRED"]
    elif kind=="INDEX":
        gaps=["INDEX_CONSTITUENT_AND_WEIGHT_VERIFICATION_REQUIRED","BENCHMARK_TRI_AND_TRACKING_EVIDENCE_REQUIRED"]
    elif kind in COMPARABLE:
        gaps=["COMPLETE_SECTOR_AND_MARKET_CAP_COVERAGE_REQUIRED","HOLDING_LIQUIDITY_AND_DERIVATIVE_EVIDENCE_REQUIRED"]
    else:
        gaps=["EXACT_CATEGORY_REQUIRED"]
    result={"status":"INSUFFICIENT_EXACT_EQUITY_EVIDENCE","category":kind,
            "exact_equity_weight_percent":None,"largest_equity_weight_percent":None,
            "top_three_equity_weight_percent":None,"equity_subset_hhi":None,
            "equity_subset_effective_holdings":None,"sector_classified_weight_percent":None,
            "unclassified_exact_equity_weight_percent":None,"sector_weights":[],
            "largest_classified_sector_weight_percent":None,
            "reported_equity_weight_percent":allocations.get("Equity"),
            "reported_debt_weight_percent":allocations.get("Debt"),
            "reported_money_market_weight_percent":allocations.get("Money market"),
            "missing_risk_evidence":gaps,"risk_rating":None,
            "notice":"Concentration is descriptive, not a risk rating. HHI and effective holdings normalize only the exact listed-equity subset; other percentages are original fund weights. Sector classifications use current matched provider profiles, not historical filing classifications. Unclassified holdings and other assets may change actual concentration."}
    weights={}
    for row in equities:
        try:
            isin=row["isin"]
            w=Decimal(str(row["weight_percent"]))
            if not isinstance(isin,str) or not ISIN.fullmatch(isin) or isin in weights or not w.is_finite() or not 0<w<=100:
                return result
            weights[isin]=w
        except (KeyError,TypeError,ValueError,InvalidOperation):
            return result
    total=sum(weights.values(),Decimal(0))
    if not 0<total<=Decimal("100.5"):
        return result
    def rounded(value):
        return float(round(value,4))
    ordered=sorted(weights.values(),reverse=True)
    hhi=sum((v/total)**2 for v in ordered)
    sectors=defaultdict(Decimal)
    for isin,weight in weights.items():
        row=sector_evidence.get(isin,{})
        sector=row.get("sector")
        if isinstance(sector,str) and sector.strip():
            sectors[" ".join(sector.casefold().split())]+=weight
    classified=sum(sectors.values(),Decimal(0))
    sector_rows=[{"sector":key,"weight_percent":rounded(weight)} for key,weight in sorted(sectors.items(),key=lambda kv:(-kv[1],kv[0]))]
    result.update(status="EXACT_EQUITY_SUBSET_ONLY",exact_equity_weight_percent=rounded(total),
        largest_equity_weight_percent=rounded(ordered[0]),top_three_equity_weight_percent=rounded(sum(ordered[:3])),
        equity_subset_hhi=rounded(hhi*10000),equity_subset_effective_holdings=rounded(1/hhi),
        sector_classified_weight_percent=rounded(classified),unclassified_exact_equity_weight_percent=rounded(total-classified),
        sector_weights=sector_rows,largest_classified_sector_weight_percent=sector_rows[0]["weight_percent"] if sector_rows else None)
    return result


def _validated_equities(report):
    """Shared exact composition checks; return ordered holdings or None."""
    allocations=report["asset_allocation_percent"]
    equities=report["equities"]
    def weight(v,lower=0,upper=100.5):
        return type(v) in (int,float) and lower<=v<=upper
    if (not isinstance(allocations,dict) or not allocations or not set(allocations)<=GROUPS
        or any(not weight(v,-100 if k=="Others" else 0,100.5) for k,v in allocations.items())
        or not weight(report["reported_weight_total_percent"],99.5,100.5)
        or abs(sum(allocations.values())-report["reported_weight_total_percent"])>.0001
        or not isinstance(equities,list) or len(equities)>1000
        or type(report["exact_equity_count"]) is not int or report["exact_equity_count"]!=len(equities)):
        return None
    seen=set()
    for holding in equities:
        isin=holding["isin"]
        if (not isinstance(isin,str) or not ISIN.fullmatch(isin) or isin in seen
            or not weight(holding["weight_percent"],0,100) or holding["weight_percent"]<=0
            or not isinstance(holding["name"],str) or len(holding["name"])>200):
            raise ValueError("INVALID_COMPOSITION_HOLDING")
        seen.add(isin)
    ordered=sorted(equities,key=lambda h:(-h["weight_percent"],h["isin"]))
    exact=report["exact_listed_equity_weight_percent"]
    top=report["top_10_exact_equity_weight_percent"]
    if (not weight(exact) or not weight(top) or top>exact+.0001
        or abs(sum(h["weight_percent"] for h in ordered)-exact)>.0001
        or abs(sum(h["weight_percent"] for h in ordered[:10])-top)>.0001
        or exact>allocations.get("Equity",0)+.0001):
        return None
    return ordered


def composition_matches(disclosures,instant=None):
    """Cheap full-sample secondary composition; no company cache or network calls.
    Distinguish a known composition outside the detailed report budget from no
    dated exact match. The existing expensive enrichment cap stays unchanged.
    """
    if not permitted() or not disclosures:
        return []
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    items=disclosures[:40]
    from collections import Counter
    counts=Counter(item.get("scheme_code") for item in items if isinstance(item,dict)
                   and isinstance(item.get("scheme_code"),str))
    result=[]
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for item in items:
                if not isinstance(item,dict):
                    continue
                code,fund=item.get("scheme_code"),item.get("fund_id")
                if (not isinstance(code,str) or not re.fullmatch(r"[0-9]{1,9}",code)
                    or counts[code]!=1 or not isinstance(fund,str) or not 0<len(fund)<=80):
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_portfolio_snapshot WHERE fund_id=?",(fund,)).fetchone()
                if not found or not fund_disclosures._day(found["collected_at"],today,2):
                    continue
                try:
                    report=json.loads(found["payload"])
                    if report.get("fund_id")!=fund or not fund_disclosures._day(report["portfolio_date"],today,60):
                        continue
                    ordered=_validated_equities(report)
                    if ordered is None:
                        continue
                    result.append({"scheme_code":code,"status":"SECONDARY_COMPOSITION_ONLY",
                        "source":"TIGZIG_AMC_DERIVED","source_url":URL,"collected_at":found["collected_at"],
                        **{k:report[k] for k in ("portfolio_date","reported_weight_total_percent",
                            "asset_allocation_percent","exact_listed_equity_weight_percent",
                            "top_10_exact_equity_weight_percent","exact_equity_count")},
                        "top_holdings":[{k:h[k] for k in ("isin","name","weight_percent")} for h in ordered[:10]],
                        "notice":"Secondary reported composition; not independently verified. Exact listed equity is a subset, not full asset or derivative coverage."})
                except (ValueError,TypeError,KeyError,AttributeError):
                    continue
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError):
        return []
    return result


def matched(disclosures,instant=None,*,include_exact_weights=False):
    if not permitted() or not disclosures:
        return []
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    result=[]
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            for item in disclosures[:40]:
                if len(result)>=5:
                    break
                fund=item.get("fund_id")
                if not fund:
                    continue
                found=db.execute("SELECT payload,collected_at FROM fund_portfolio_snapshot WHERE fund_id=?",(fund,)).fetchone()
                if not found or not fund_disclosures._day(found["collected_at"],today,2):
                    continue
                try:
                    report=json.loads(found["payload"])
                    if report.get("fund_id")!=fund or not fund_disclosures._day(report["portfolio_date"],today,60):
                        continue
                    equities=_validated_equities(report)
                    if equities is None:
                        continue
                    report.pop("equities")
                except (ValueError,TypeError,KeyError,AttributeError):
                    continue
                from .fund_underlying_research import summarize, load, exact_sector_evidence
                reports=load(equities,instant)
                sector_evidence=exact_sector_evidence(equities,instant,reports)
                item_report={**report,**company_coverage(equities,instant),
                    "underlying_research":summarize(equities,instant,reports),
                    "concentration_research":concentration(equities,sector_evidence,item.get("category"),report["asset_allocation_percent"]),
                    "scheme_code":item["scheme_code"],"scheme_name":item["scheme_name"],
                    "collected_at":found["collected_at"],"top_holdings":equities[:10],
                    "status":"SECONDARY_COMPOSITION_ONLY"}
                # Private service only: compact full exact weights, no top-ten truncation.
                # Do not silently truncate large portfolios or normalize reported weights.
                if include_exact_weights and len(equities)<=500:
                    item_report["exact_equity_weights"]={h["isin"]:h["weight_percent"] for h in equities}
                    item_report["exact_sector_evidence"]=sector_evidence
                result.append(item_report)
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


def research_identities(instant=None):
    """Public disclosed equity identifiers only, no personal portfolio data."""
    if not permitted():
        return []
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    weights={}
    largest={}
    try:
        with nav_catalog._LOCK,closing(nav_catalog._connect()) as db:
            # Evaluate all accepted fresh portfolios within the original file
            # row budget, not an alphabetical first-100 subset. Stream rows to
            # bound memory and keep the provider research cap at 200 identities.
            for row in db.execute("SELECT fund_id,payload,collected_at FROM fund_portfolio_snapshot"):
                try:
                    if not fund_disclosures._day(row["collected_at"],today,2):
                        continue
                    report=json.loads(row["payload"])
                    if report.get("fund_id")!=row["fund_id"] or not fund_disclosures._day(report["portfolio_date"],today,60):
                        continue
                    holdings=_validated_equities(report)
                    if holdings is None:continue
                    for holding in holdings:
                        isin=holding["isin"]
                        weight=Decimal(str(holding["weight_percent"]))
                        weights[isin]=weights.get(isin,Decimal(0))+weight
                        largest[isin]=max(largest.get(isin,Decimal(0)),weight)
                except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation):
                    continue
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError,InvalidOperation):
        return []
    # Sum of original public fund weights is a collection priority, not an
    # aggregate market exposure or investment ranking. Keep the existing cap.
    return sorted(weights,key=lambda isin:(-weights[isin],-largest[isin],isin))[:200]
