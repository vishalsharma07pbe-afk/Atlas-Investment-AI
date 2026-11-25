"""Current reported holdings x historical provider fundamentals.

Weights are original fund percentages. Coverage is not forward forecast
coverage, and undated relative valuations do not establish attractiveness.
"""
from collections import defaultdict
from contextlib import closing
from datetime import datetime,timedelta
from math import isfinite
import json
import os
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

from . import automatic_company_evidence as company

IST=ZoneInfo("Asia/Kolkata")
METRICS=("REVENUE","NET_PROFIT","OPERATING_CASH_FLOW")
PERIOD=re.compile(r"20[0-9]{2}-(?:0[1-9]|1[0-2])")


def _number(value):
    return type(value) in (int,float) and isfinite(value)


def load(equities,instant):
    if not company.permitted():
        return {}
    path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3"))
    ids=sorted({h["isin"] for h in equities})[:1000]
    if not ids:
        return {}
    result={}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=2)) as db:
            # Bounded batches avoid a query per holding and SQLite variable limits.
            for start in range(0,len(ids),200):
                chunk=ids[start:start+200]
                marks=",".join("?" for _ in chunk)
                rows=db.execute(f"""SELECT isin,payload FROM automatic_company_evidence WHERE isin IN ({marks})
                    AND status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?""",
                    (*chunk,(instant-timedelta(hours=24)).isoformat(),instant.isoformat()))
                for isin,payload in rows:
                    try:
                        report=json.loads(payload)
                        stamp=datetime.fromisoformat(report["retrieved_at"])
                        if (report.get("isin")==isin and stamp.tzinfo is not None
                            and instant-timedelta(hours=24)<=stamp<=instant):
                            result[isin]=report
                    except (ValueError,TypeError,AttributeError,KeyError):
                        continue
    except (OSError,sqlite3.Error):
        return {}
    return result


def summarize(equities,instant,reports=None):
    reports=load(equities,instant) if reports is None else reports
    today=instant.astimezone(IST).date()
    sectors=defaultdict(float)
    trends=defaultdict(lambda:{"coverage":0.0,"increased":0.0,"decreased":0.0,"unchanged":0.0,"negative_latest":0.0})
    quality=0.0
    flagged=0.0
    valuation=defaultdict(lambda:{"coverage":0.0,"above":0.0,"below":0.0,"equal":0.0})
    seen=set()
    covered=0.0
    for h in equities:
        isin,w=h.get("isin"),h.get("weight_percent")
        if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or not _number(w) or not 0<w<=100 or isin in seen:
            return {"status":"INVALID_HOLDING_IDENTITIES","notice":"No metrics calculated for conflicting holding weights."}
        seen.add(isin)
        raw=reports.get(isin)
        if not isinstance(raw,dict) or raw.get("isin")!=isin:
            continue
        try:
            report=company._enrich(dict(raw),today)
            sections=report["sections"]
            profile=sections.get("profile",{})
            sector=(profile.get("data") or {}).get("sector") if profile.get("status")=="AVAILABLE" else None
            if isinstance(sector,str) and sector.strip():
                sectors[sector.strip()[:180]]+=w
            current=[]
            for metric in report["financial_trends"]["items"]:
                latest,prior=metric.get("latest_period"),metric.get("previous_period")
                if (metric["metric"] not in METRICS or metric.get("statement_type")!="consolidated"
                    or metric.get("period_basis")!="DECLARED_ANNUAL_MONTH_END" or metric.get("latest_period_may_be_stale") is not False
                    or not isinstance(latest,str) or not PERIOD.fullmatch(latest)
                    or not isinstance(prior,str) or not PERIOD.fullmatch(prior)
                    or not _number(metric.get("latest_value")) or not _number(metric.get("previous_value"))):
                    continue
                current.append(metric)
                bucket=trends[(metric["metric"],prior,latest)]
                bucket["coverage"]+=w
                delta=metric["latest_value"]-metric["previous_value"]
                bucket["increased" if delta>0 else "decreased" if delta<0 else "unchanged"]+=w
                if metric["latest_value"]<0:
                    bucket["negative_latest"]+=w
            if current:
                quality+=w
                if any(x["latest_value"]<0 or x["latest_value"]<x["previous_value"] for x in current):
                    flagged+=w
            for ratio in report["fundamental_quality"]["valuation"]["comparisons"]:
                key=ratio["metric"]
                if key not in ("PE","PB","EV_EBITDA"):
                    continue
                bucket=valuation[key]
                bucket["coverage"]+=w
                bucket[{"ABOVE_SECTOR":"above","BELOW_SECTOR":"below","AT_SECTOR":"equal"}[ratio["position"]]]+=w
            if raw.get("available_sections",0)>0:
                covered+=w
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            # A malformed cached report cannot supply an outlook.
            continue
    def rounded(data):
        return {k:round(v,4) for k,v in data.items()}
    return {"status":"REPORTED_HISTORICAL_DRIVERS_ONLY" if covered else "COLLECTING_COMPANY_EVIDENCE",
        "cached_report_weight_percent":round(covered,4),
        "sector_classified_weight_percent":round(sum(sectors.values()),4),
        "sector_weights":[{"sector":k,"weight_percent":round(v,4)} for k,v in sorted(sectors.items(),key=lambda kv:(-kv[1],kv[0]))],
        "annual_statement_weight_percent":round(quality,4),"deterioration_review_weight_percent":round(flagged,4),
        "annual_trends":[{"metric":k[0],"previous_period":k[1],"latest_period":k[2],**rounded(v)} for k,v in sorted(trends.items())],
        "relative_valuation":[{"metric":k,**rounded(v),"period_status":"UNVERIFIED"} for k,v in sorted(valuation.items())],
        "forward_earnings_coverage_percent":None,"valuation_attractiveness":None,
        "notice":"Historical provider reports weighted by disclosed fund exposure, grouped by exact annual periods. Sector and trend weights are partial, not normalized. Relative valuation ratios have unverified observation dates. No forecast, fair value or qualified Growth Outlook."}
