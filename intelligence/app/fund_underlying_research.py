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
ANNUAL_HISTORY_CACHE_DAYS=company.ANNUAL_HISTORY_CACHE_DAYS
ANNUAL_SECTIONS=company.ANNUAL_SECTIONS


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
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('automatic_company_evidence','automatic_company_annual_archive')")}
            if "automatic_company_evidence" not in tables:
                return {}
            for start in range(0,len(ids),200):
                chunk=ids[start:start+200]
                marks=",".join("?" for _ in chunk)
                rows=db.execute(f"""SELECT isin,payload FROM automatic_company_evidence WHERE isin IN ({marks})
                    AND status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?""",
                    (*chunk,(instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)).isoformat(),instant.isoformat()))
                for isin,payload in rows:
                    try:
                        report=json.loads(payload)
                        stamp=datetime.fromisoformat(report["retrieved_at"])
                        if (report.get("isin")!=isin or stamp.tzinfo is None
                            or not instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)<=stamp<=instant):
                            continue
                        if stamp<instant-timedelta(hours=24):
                            # Retrieval age is not a financial period. Reuse only
                            # explicitly annual consolidated statements, not stale
                            # ratios, profiles, ownership or corporate actions.
                            sections={}
                            for key in ANNUAL_SECTIONS:
                                block=report["sections"].get(key,{})
                                data=block.get("data")
                                if (block.get("status")=="AVAILABLE" and isinstance(data,dict)
                                    and data.get("statement_type")=="consolidated"
                                    and data.get("time_period")=="yearly"
                                    and (block.get("source") or {}).get("provider")=="UPSTOX"):
                                    sections[key]=block
                            if not sections:
                                continue
                            report={**report,"sections":sections,"available_sections":len(sections),
                                    "historical_cache_only":True}
                        result[isin]=report
                    except (ValueError,TypeError,AttributeError,KeyError):
                        continue
                if "automatic_company_annual_archive" in tables:
                    for isin,payload in db.execute(f"""SELECT isin,payload FROM automatic_company_annual_archive WHERE isin IN ({marks})
                        AND retrieved_at BETWEEN ? AND ?""",
                        (*chunk,(instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)).isoformat(),instant.isoformat())):
                        try:
                            archived=company.annual_capture(json.loads(payload),isin,instant)
                            if not archived:
                                continue
                            current=result.get(isin)
                            if current is None:
                                result[isin]=archived
                            elif current.get("historical_cache_only") is not True and not any(
                                current["sections"].get(key,{}).get("status")=="AVAILABLE" for key in ANNUAL_SECTIONS):
                                # Keep current nonannual evidence separate from a
                                # coherent earlier annual capture; do not mix two
                                # annual captures or promote old ratios/actions.
                                sections={**current["sections"],**archived["sections"]}
                                result[isin]={**current,"sections":sections,
                                    "historical_annual_capture_at":archived["retrieved_at"]}
                        except (ValueError,TypeError,AttributeError,KeyError):
                            continue
    except (OSError,sqlite3.Error):
        return {}
    return result


def exact_sector_evidence(equities,instant,reports):
    """Private service working metadata; only fresh exact-ISIN provider profiles."""
    result={}
    for h in equities:
        isin=h.get("isin")
        raw=reports.get(isin)
        if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or not isinstance(raw,dict) or raw.get("isin")!=isin:
            continue
        try:
            stamp=datetime.fromisoformat(raw["retrieved_at"])
            profile=raw["sections"]["profile"]
            source=profile.get("source") or {}
            sector=profile["data"]["sector"]
            if (stamp.tzinfo is not None and instant-timedelta(hours=24)<=stamp<=instant
                and profile.get("status")=="AVAILABLE" and source.get("provider")=="UPSTOX"
                and isinstance(sector,str) and 0<len(sector.strip())<=180):
                result[isin]={"sector":sector.strip(),"retrieved_at":stamp.isoformat(),"provider":"UPSTOX"}
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
    return result


MULTI_METRICS=("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW")


def _multi_year_exposure(holdings):
    """Aggregate only per-company diagnostics produced by the shared quality engine.

    Keep distinct fiscal windows separate, and use original reported fund weights
    rather than reweighting the researched subset to 100%.
    """
    metrics=defaultdict(lambda:{"coverage":0.0,"consistent_increases":0.0,
                                "repeated_declines":0.0,"nonpositive_observations":0.0})
    cash=defaultdict(lambda:{"coverage":0.0,"below_profit":0.0,"negative_cash_years":0.0})
    growth=defaultdict(lambda:{"coverage":0.0,"positive":0.0,"negative":0.0,"flat":0.0,"weighted_sum":0.0})
    covered=flagged=cash_covered=0.0
    for weight,quality in holdings:
        assessed=review=False
        for row in quality.get("metrics",[]):
            key=row["metric"]
            if key not in MULTI_METRICS:
                continue
            periods=[p["period"] for p in row["observations"]]
            if len(periods)!=4 or any(not PERIOD.fullmatch(p) for p in periods):
                continue
            bucket=metrics[(key,*periods)]
            bucket["coverage"]+=weight
            assessed=True
            values=[p.get("value") for p in row["observations"]]
            # All four values must be positive; loss-to-profit transitions
            # do not have an economically meaningful CAGR.
            if all(_number(v) and v>0 for v in values):
                from math import expm1,log
                try:
                    cagr=100*expm1((log(values[-1])-log(values[0]))/3)
                except (ValueError,OverflowError):
                    cagr=None
                if _number(cagr) and -100<cagr<=1_000_000:
                    g=growth[(key,*periods)]
                    g["coverage"]+=weight
                    g["weighted_sum"]+=weight*cagr
                    g["positive" if cagr>0 else "negative" if cagr<0 else "flat"]+=weight
            if row["increasing_years"]==3 and row["nonpositive_years"]==0:
                bucket["consistent_increases"]+=weight
            if row["decreasing_years"]>=2:
                bucket["repeated_declines"]+=weight
                review=True
            if row["nonpositive_years"]>0:
                bucket["nonpositive_observations"]+=weight
                review=True
        conversion=quality.get("cash_conversion")
        if conversion is not None:
            key=(conversion["first_period"],conversion["last_period"])
            bucket=cash[key]
            bucket["coverage"]+=weight
            cash_covered+=weight
            assessed=True
            if conversion["cumulative_operating_cash"]<conversion["cumulative_net_profit"]:
                bucket["below_profit"]+=weight
                review=True
            if conversion["negative_cash_years"]>0:
                bucket["negative_cash_years"]+=weight
                review=True
        if assessed:
            covered+=weight
        if review:
            flagged+=weight
    def rounded(row):
        return {k:round(v,4) for k,v in row.items()}
    return {"status":"REPORTED_MULTI_YEAR_EXPOSURE" if covered else "INSUFFICIENT_MULTI_YEAR_EVIDENCE",
        "assessed_weight_percent":round(covered,4),"review_weight_percent":round(flagged,4),
        "cash_conversion_coverage_percent":round(cash_covered,4),
        "metrics":[{"metric":k[0],"periods":list(k[1:]),**rounded(v)} for k,v in sorted(metrics.items())],
        "cash_conversion":[{"first_period":k[0],"last_period":k[1],**rounded(v)} for k,v in sorted(cash.items())],
        "historical_growth":[{"metric":k[0],"periods":list(k[1:]),
            "coverage_weight_percent":round(v["coverage"],4),
            "positive_growth_weight_percent":round(v["positive"],4),
            "negative_growth_weight_percent":round(v["negative"],4),
            "flat_growth_weight_percent":round(v["flat"],4),
            "covered_subset_weighted_cagr_percent":round(v["weighted_sum"]/v["coverage"],4)}
            for k,v in sorted(growth.items()) if v["coverage"]>0],
        "notice":"Original reported fund weights, not normalized equity weights. Review categories can overlap; total review weight counts each holding once. Four-year historical provider reports, not forecasts or independently verified business quality. Cash conversion is not free cash flow and differs by sector."}


def summarize(equities,instant,reports=None):
    reports=load(equities,instant) if reports is None else reports
    today=instant.astimezone(IST).date()
    sectors=defaultdict(float)
    trends=defaultdict(lambda:{"coverage":0.0,"increased":0.0,"decreased":0.0,"unchanged":0.0,"negative_latest":0.0})
    quality=0.0
    flagged=0.0
    valuation=defaultdict(lambda:{"coverage":0.0,"above":0.0,"below":0.0,"equal":0.0})
    sector_comparisons=defaultdict(list)
    seen=set()
    covered=0.0
    exact_weight=0.0
    multi_year=[]
    historical_cache_weight=0.0
    margin_trends=defaultdict(lambda:{"coverage":0.0,"improved":0.0,"deteriorated":0.0,"unchanged":0.0,"weighted_change":0.0})
    for h in equities:
        isin,w=h.get("isin"),h.get("weight_percent")
        if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or not _number(w) or not 0<w<=100 or isin in seen:
            return {"status":"INVALID_HOLDING_IDENTITIES","notice":"No metrics calculated for conflicting holding weights."}
        seen.add(isin)
        exact_weight+=w
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
            # Only the existing matched-unit company margin calculations, with
            # explicit fiscal month-end periods. Do not combine unlike ratios.
            for metric in report["fundamental_quality"]["derived_metrics"]:
                key=metric.get("metric")
                prior,latest=metric.get("previous_period"),metric.get("latest_period")
                change=metric.get("change")
                if (key not in ("NET_MARGIN","OPERATING_MARGIN") or metric.get("unit")!="PERCENT"
                    or not isinstance(prior,str) or not PERIOD.fullmatch(prior)
                    or not isinstance(latest,str) or not PERIOD.fullmatch(latest)
                    or int(latest[:4])-int(prior[:4])!=1 or prior[5:]!=latest[5:]
                    or not _number(change) or abs(change)>1_000_000):
                    continue
                bucket=margin_trends[(key,prior,latest)]
                bucket["coverage"]+=w
                bucket["improved" if change>0 else "deteriorated" if change<0 else "unchanged"]+=w
                bucket["weighted_change"]+=w*change
            for ratio in report["fundamental_quality"]["valuation"]["comparisons"]:
                key=ratio["metric"]
                if key not in ("PE","PB","EV_EBITDA"):
                    continue
                bucket=valuation[key]
                bucket["coverage"]+=w
                bucket[{"ABOVE_SECTOR":"above","BELOW_SECTOR":"below","AT_SECTOR":"equal"}[ratio["position"]]]+=w
            # Separate provider-relative financial quality from dated annual
            # evidence. Retrieval freshness does not date the ratio observation.
            # Use the same exact ISIN and require a fresh provider sector profile.
            if raw.get("historical_cache_only") is not True:
                exact=exact_sector_evidence([h],instant,{isin:raw}).get(isin)
                source=sections.get("ratios",{}).get("source") or {}
                if exact and source.get("provider")=="UPSTOX":
                    try:
                        stamp=datetime.fromisoformat(source.get("retrieved_at",""))
                    except (ValueError,TypeError):
                        stamp=None
                    if stamp is not None and stamp.tzinfo is not None and instant-timedelta(hours=24)<=stamp<=instant:
                        for ratio in report["fundamental_quality"]["sector_comparisons"]:
                            key=ratio["metric"]
                            if key not in ("PE","PB","EV_EBITDA","ROE","ROCE","ROA","DEBT_EQUITY","INTEREST_COVERAGE"):
                                continue
                            value=ratio["premium_discount_percent"] if key in ("PE","PB","EV_EBITDA") else ratio["difference"]
                            if not _number(value) or abs(value)>1_000_000:
                                continue
                            sector_key=" ".join(exact["sector"].casefold().split())
                            sector_comparisons[(sector_key,key)].append((value,w))
            if raw.get("available_sections",0)>0:
                if raw.get("historical_cache_only") is True:
                    if current:
                        historical_cache_weight+=w
                else:
                    covered+=w
                    if raw.get("historical_annual_capture_at") and current:
                        historical_cache_weight+=w
                multi_year.append((w,report["fundamental_quality"]["multi_year_quality"]))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            # A malformed cached report cannot supply an outlook.
            continue
    if exact_weight>100.5000001:
        return {"status":"INVALID_HOLDING_IDENTITIES","notice":"No metrics calculated for conflicting holding weights."}
    def rounded(data):
        return {k:round(v,4) for k,v in data.items()}
    def sector_row(key,observations):
        sector,metric=key
        weight=sum(w for _,w in observations)
        # Weighted median of the covered holdings, not the sector market median.
        ordered=sorted(observations)
        cumulative=0.0
        median=ordered[-1][0]
        for value,w in ordered:
            cumulative+=w
            if cumulative>=weight/2:
                median=value
                break
        return {"sector":sector,"metric":metric,
            "comparison_unit":"PERCENT_PREMIUM_DISCOUNT" if metric in ("PE","PB","EV_EBITDA") else
                              "PERCENTAGE_POINTS" if metric in ("ROE","ROCE","ROA") else "RATIO_DIFFERENCE",
            "holding_count":len(observations),"coverage_weight_percent":round(weight,4),
            "above_sector_weight_percent":round(sum(w for value,w in observations if value>0),4),
            "below_sector_weight_percent":round(sum(w for value,w in observations if value<0),4),
            "equal_sector_weight_percent":round(sum(w for value,w in observations if value==0),4),
            "covered_subset_weighted_difference":round(sum(value*w for value,w in observations)/weight,4),
            "covered_subset_weighted_median":round(median,4),
            "observation_period":"UNVERIFIED","provider":"UPSTOX"}
    comparisons=[sector_row(k,v) for k,v in sorted(sector_comparisons.items())]
    multi=_multi_year_exposure(multi_year)
    multi["exact_equity_weight_percent"]=round(exact_weight,4)
    multi["unassessed_exact_equity_weight_percent"]=round(max(0.0,exact_weight-multi["assessed_weight_percent"]),4)
    return {"status":"REPORTED_HISTORICAL_DRIVERS_ONLY" if covered or historical_cache_weight else "COLLECTING_COMPANY_EVIDENCE",
        "multi_year_quality":multi,
        "cached_report_weight_percent":round(covered,4),
        "annual_history_cache_weight_percent":round(historical_cache_weight,4),
        "annual_history_cache_max_age_days":ANNUAL_HISTORY_CACHE_DAYS,
        "sector_classified_weight_percent":round(sum(sectors.values()),4),
        "sector_weights":[{"sector":k,"weight_percent":round(v,4)} for k,v in sorted(sectors.items(),key=lambda kv:(-kv[1],kv[0]))],
        "annual_statement_weight_percent":round(quality,4),"deterioration_review_weight_percent":round(flagged,4),
        "annual_trends":[{"metric":k[0],"previous_period":k[1],"latest_period":k[2],**rounded(v)} for k,v in sorted(trends.items())],
        "relative_valuation":[{"metric":k,**rounded(v),"period_status":"UNVERIFIED"} for k,v in sorted(valuation.items())],
        "historical_margin_changes":[{"metric":k[0],"previous_period":k[1],"latest_period":k[2],
            "coverage_weight_percent":round(v["coverage"],4),"improved_weight_percent":round(v["improved"],4),
            "deteriorated_weight_percent":round(v["deteriorated"],4),"unchanged_weight_percent":round(v["unchanged"],4),
            "covered_subset_weighted_change_pp":round(v["weighted_change"]/v["coverage"],4)}
            for k,v in sorted(margin_trends.items()) if v["coverage"]>0],
        "sector_relative_financial_quality":{"status":"REPORTED_UNDATED_COMPARISONS" if comparisons else "UNAVAILABLE",
            "items":comparisons,"notice":"Fresh retrieval, unknown ratio observation date. Original fund weight per sector and metric; weighted mean and median refer only to covered holdings. No universal quality threshold, fair value, forward earnings or investment qualification."},
        "forward_earnings_coverage_percent":None,"valuation_attractiveness":None,
        "notice":"Historical provider reports weighted by disclosed fund exposure, grouped by exact annual periods. Sector and trend weights are partial, not normalized. Annual statements may be reused for seven days with existing fiscal-period checks. Retained coherent annual captures are historical-only; fresh company coverage requires independently current nonannual or annual evidence. Historical annual weight can overlap fresh nonannual coverage. Ratios and profiles still require retrieval within 24 hours. Relative valuation ratios have unverified observation dates. No forecast, fair value or qualified Growth Outlook."}
