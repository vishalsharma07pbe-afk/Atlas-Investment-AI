"""Deterministic, fail-closed mutual-fund research rankings.

The connected catalog is useful for discovery but is not silently promoted into
recommendations. Rankings require dated, source-attributed evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from math import isfinite
import re
from decimal import Decimal, InvalidOperation
import hashlib
import json

from . import nav_catalog, fund_disclosures, fund_portfolios
from .market_client import backend_json
from .fund_categories import CATEGORIES, LABELS as OFFICIAL_CATEGORY_LABELS, DEBT, SPECIALIZED, COMPARABLE

METHODOLOGY_VERSION = "MF-RESEARCH-1.1.0"
RISK_LEVELS = ("LOW","MODERATE","HIGH")

@dataclass(frozen=True)
class FundEvidence:
    identifier:str
    name:str
    category:str
    category_verified:bool
    plan:str
    option:str
    passive:bool=False
    benchmark:str|None=None
    nav:Decimal|None=None
    nav_date:str|None=None
    nav_age_days:int|None=None
    history_years:float=0
    returns_1y:float|None=None
    returns_3y:float|None=None
    returns_5y:float|None=None
    peer_percentile:float|None=None
    benchmark_hit_rate:float|None=None
    worst_rolling_return:float|None=None
    max_drawdown:float|None=None
    volatility:float|None=None
    expense_ratio:float|None=None
    tracking_difference:float|None=None
    tracking_error:float|None=None
    riskometer:str|None=None
    riskometer_date:str|None=None
    portfolio_age_days:int|None=None
    portfolio_coverage:float|None=None
    earnings_coverage:float|None=None
    valuation_coverage:float|None=None
    earnings_growth:float|None=None
    valuation_attractiveness:float|None=None
    sector_driver_score:float|None=None
    concentration_risk:float|None=None
    liquidity_score:float|None=None
    index_outlook_coverage:float|None=None

def infer_category(name:str)->str|None:
    value=" "+" ".join(name.upper().replace("-"," ").split())+" "
    if " INDEX FUND " in value or " INDEX " in value:
        return "INDEX"
    if " LARGE AND MID CAP " in value or " LARGE & MID CAP " in value:
        return "LARGE_MID_CAP"
    for phrase,category in ((" MULTI CAP ","MULTI_CAP"),(" AGGRESSIVE HYBRID ","AGGRESSIVE_HYBRID"),(" CORPORATE BOND ","CORPORATE_BOND"),(" SHORT DURATION ","SHORT_DURATION")):
        if phrase in value:return category
    for phrase,category in ((" LARGE CAP ","LARGE_CAP"),(" MID CAP ","MID_CAP"),
                            (" SMALL CAP ","SMALL_CAP"),(" FLEXI CAP ","FLEXI_CAP")):
        if phrase in value:return category
    return None

def infer_benchmark(name:str)->str|None:
    value=name.upper()
    for label in ("NIFTY NEXT 50","NIFTY 50","NIFTY MIDCAP 150","NIFTY SMALLCAP 250",
                  "NIFTY 100","NIFTY 200","NIFTY 500","S&P BSE SENSEX","SENSEX"):
        if label in value:return label
    return None

def suitability(category:str,horizon_months:int,risk_tolerance:str):
    flags=[]
    if category in DEBT:
        flags.append("CREDIT_DURATION_AND_LIQUIDITY_REVIEW_REQUIRED")
    elif horizon_months<=36:
        flags.append("POOR_FIT_FOR_36_MONTH_GOAL")
    elif horizon_months<60:
        flags.append("SHORT_HORIZON_FOR_EQUITY")
    if category=="AGGRESSIVE_HYBRID":
        flags.append("EQUITY_DEBT_ALLOCATION_REVIEW_REQUIRED")
    if category=="INDEX":
        flags.append("UNDERLYING_INDEX_SUITABILITY_UNVERIFIED")
    if risk_tolerance=="LOW" and category in {"MID_CAP","SMALL_CAP","LARGE_MID_CAP","MULTI_CAP"}:
        flags.append("ABOVE_SELECTED_RISK_TOLERANCE")
    elif risk_tolerance=="MODERATE" and category=="SMALL_CAP":
        flags.append("ABOVE_SELECTED_RISK_TOLERANCE")
    return {"status":"POOR_FIT" if flags else "POTENTIALLY_SUITABLE",
            "flags":flags,"horizon_months":horizon_months,"risk_tolerance":risk_tolerance}

def _bounded(value,low=None,high=None):
    return (not isinstance(value,bool) and isinstance(value,(int,float,Decimal)) and isfinite(value)
            and (low is None or value>=low) and (high is None or value<=high))


def _common(f:FundEvidence):
    missing=[]
    if f.category_verified is not True:missing.append("OFFICIAL_CATEGORY")
    if f.plan!="DIRECT" or f.option!="GROWTH":missing.append("EXACT_DIRECT_GROWTH_PLAN")
    if f.category in SPECIALIZED:missing.append("CATEGORY_SPECIFIC_RISK_MODEL_REQUIRED")
    if f.passive!=(f.category=="INDEX"):missing.append("CATEGORY_STRATEGY_MISMATCH")
    if not _bounded(f.nav,Decimal("0.000001")) or not f.nav_date or not _bounded(f.nav_age_days,0,7):missing.append("FRESH_DATED_NAV")
    if f.riskometer not in {"LOW","LOW_TO_MODERATE","MODERATE","MODERATELY_HIGH","HIGH","VERY_HIGH"} or not f.riskometer_date:missing.append("OFFICIAL_RISKOMETER")
    if not _bounded(f.history_years,3):missing.append("THREE_YEAR_NAV_HISTORY")
    if not _bounded(f.expense_ratio,0,100):missing.append("EXPENSE_RATIO")
    return missing


def _missing_top(f:FundEvidence):
    missing=_common(f)
    if f.passive:
        if not f.benchmark:missing.append("UNDERLYING_INDEX")
        if not _bounded(f.tracking_difference):missing.append("TRACKING_DIFFERENCE")
        if not _bounded(f.tracking_error,0):missing.append("TRACKING_ERROR")
    else:
        for value,label in ((f.returns_1y,"ONE_YEAR_RETURN"),(f.returns_3y,"THREE_YEAR_RETURN"),
                            (f.peer_percentile,"PEER_PERCENTILE"),(f.benchmark_hit_rate,"BENCHMARK_HIT_RATE"),
                            (f.worst_rolling_return,"WORST_ROLLING_RETURN"),(f.max_drawdown,"MAX_DRAWDOWN"),
                            (f.volatility,"VOLATILITY")):
            bounds={"PEER_PERCENTILE":(0,100),"BENCHMARK_HIT_RATE":(0,1),"MAX_DRAWDOWN":(-100,0),"VOLATILITY":(0,None)}
            if not _bounded(value,*bounds.get(label,(-100,None))):missing.append(label)
    return missing

def _missing_growth(f:FundEvidence):
    missing=_common(f)
    if not _bounded(f.portfolio_age_days,0,60):missing.append("RECENT_PORTFOLIO_DISCLOSURE")
    if not _bounded(f.portfolio_coverage,.8,1):missing.append("PORTFOLIO_COVERAGE_80_PERCENT")
    if f.passive:
        if not f.benchmark:missing.append("UNDERLYING_INDEX")
        if not _bounded(f.index_outlook_coverage,.7,1):missing.append("INDEX_OUTLOOK_COVERAGE_70_PERCENT")
        if not _bounded(f.tracking_difference):missing.append("TRACKING_DIFFERENCE")
    else:
        if not _bounded(f.earnings_coverage,.7,1):missing.append("EARNINGS_COVERAGE_70_PERCENT")
        if not _bounded(f.valuation_coverage,.6,1):missing.append("VALUATION_COVERAGE_60_PERCENT")
        for value,label in ((f.earnings_growth,"FORWARD_EARNINGS_GROWTH"),
                            (f.valuation_attractiveness,"VALUATION_EVIDENCE"),
                            (f.sector_driver_score,"SECTOR_DRIVERS"),(f.concentration_risk,"CONCENTRATION"),
                            (f.liquidity_score,"LIQUIDITY")):
            if not _bounded(value, -100 if label=="FORWARD_EARNINGS_GROWTH" else 0, None if label=="FORWARD_EARNINGS_GROWTH" else 100):missing.append(label)
    return missing

def _top_score(f:FundEvidence):
    if f.passive:
        return max(0,100-(abs(f.tracking_difference or 0)*20+abs(f.tracking_error or 0)*15+(f.expense_ratio or 0)*10))
    peer=max(0,min(100,f.peer_percentile or 0))
    hit=max(0,min(1,f.benchmark_hit_rate or 0))*100
    worst=max(0,min(100,50+(f.worst_rolling_return or 0)*2))
    draw=max(0,min(100,100-abs(f.max_drawdown or 0)*2))
    vol=max(0,min(100,100-(f.volatility or 0)*2))
    cost=max(0,min(100,100-(f.expense_ratio or 0)*40))
    return peer*.25+hit*.25+worst*.20+draw*.15+vol*.10+cost*.05

def _growth_score(f:FundEvidence):
    if f.passive:
        return max(0,min(100,(f.index_outlook_coverage or 0)*70+30-abs(f.tracking_difference or 0)*10))
    earnings=max(0,min(100,50+(f.earnings_growth or 0)*2))
    valuation=max(0,min(100,f.valuation_attractiveness or 0))
    drivers=max(0,min(100,f.sector_driver_score or 0))
    concentration=max(0,min(100,100-(f.concentration_risk or 0)))
    liquidity=max(0,min(100,f.liquidity_score or 0))
    return earnings*.30+valuation*.25+drivers*.20+concentration*.15+liquidity*.10

def _confidence(f:FundEvidence,kind:str):
    if kind=="TOP":
        coverage=1-len(_missing_top(f))/12
    else:coverage=1-len(_missing_growth(f))/10
    return "HIGH" if coverage>=.9 else "MEDIUM" if coverage>=.75 else "LOW"

def rank_candidates(candidates:list[FundEvidence],category:str,horizon_months:int,risk_tolerance:str):
    fit=suitability(category,horizon_months,risk_tolerance)
    top=[];growth=[];excluded=[]
    from collections import Counter
    counts=Counter(f.identifier for f in candidates if f.category==category)
    for fund in candidates:
        if fund.category!=category:continue
        top_missing=_missing_top(fund);growth_missing=_missing_growth(fund)
        if counts[fund.identifier]>1:
            if any(row["identifier"]==fund.identifier for row in excluded):continue
            top_missing.append("DUPLICATE_SCHEME_IDENTITY");growth_missing.append("DUPLICATE_SCHEME_IDENTITY")
        if fit["status"]=="POOR_FIT":
            top_missing.append("SELECTED_HORIZON_OR_RISK_REVIEW_REQUIRED");growth_missing.append("SELECTED_HORIZON_OR_RISK_REVIEW_REQUIRED")
        if not top_missing:
            score=round(_top_score(fund),4)
            top.append({"fund":asdict(fund),"score":score,"atlas_research_rating":"A" if score>=80 else "B" if score>=65 else "C",
                        "evidence_confidence":_confidence(fund,"TOP"),"suitability":fit,
                        "qualification_reason":"Qualified under versioned category-relative performance and risk gates.",
                        "key_risk":"Past performance and benchmark-relative strength may not persist."})
        if not growth_missing:
            score=round(_growth_score(fund),4)
            growth.append({"fund":asdict(fund),"score":score,"atlas_research_rating":"A" if score>=80 else "B" if score>=65 else "C",
                           "evidence_confidence":_confidence(fund,"GROWTH"),"suitability":fit,
                           "qualification_reason":"Qualified using current portfolio, earnings, valuation and risk evidence.",
                           "key_risk":"Forward evidence can change as holdings, earnings and valuations change."})
        if top_missing or growth_missing:
            excluded.append({"identifier":fund.identifier,"top_performer_missing":top_missing,
                             "growth_outlook_missing":growth_missing})
    top.sort(key=lambda x:(-x["score"],x["fund"]["identifier"]));growth.sort(key=lambda x:(-x["score"],x["fund"]["identifier"]))
    for rows in (top,growth):
        for i,row in enumerate(rows[:5],1):row["rank"]=i
    return {"top_performers":top[:5],"growth_outlook":growth[:5],"top_eligible_count":len(top),"growth_eligible_count":len(growth),"excluded":excluded,"suitability":fit}

def _catalog_candidates(category:str):
    with nav_catalog._LOCK,nav_catalog._connect() as db:
        rows=db.execute("SELECT * FROM provider_nav_schemes ORDER BY scheme_name").fetchall()
    candidates=[];matched=0;direct_growth=0
    for row in rows:
        inferred=infer_category(row["scheme_name"])
        if inferred!=category:continue
        matched+=1;meta=json.loads(row["metadata_json"]);plan=str(meta.get("plan") or "").upper()
        option="GROWTH" if "GROWTH" in row["scheme_name"].upper() and "IDCW" not in row["scheme_name"].upper() else "OTHER"
        if plan=="DIRECT" and option=="GROWTH":direct_growth+=1
        candidates.append(FundEvidence(identifier=row["provider_key"],name=row["scheme_name"],category=category,
          category_verified=False,plan=plan,option=option,passive=category=="INDEX",benchmark=infer_benchmark(row["scheme_name"]),
          nav=Decimal(row["nav"]),nav_date=row["nav_date"] if row["nav_date_status"]=="DECLARED" else None,
          nav_age_days=None,history_years=0))
    return candidates,{"name_matched_schemes":matched,"exact_direct_growth_schemes":direct_growth,
                       "official_category_verified":0,"dated_nav_history_eligible":0,"portfolio_disclosures_eligible":0}

def _official_history_candidates(historical,category,today):
    """Join only dated, explicitly identified Direct Growth evidence by AMFI code.
    Do not merge an inferred Upstox ticker/name match or invent missing factors."""
    label=OFFICIAL_CATEGORY_LABELS[category]
    items=historical.get("research_candidates",historical.get("items",[]))
    if not isinstance(items,list) or len(items)>40:
        return []
    ids=[r.get("scheme_code") for r in items if isinstance(r,dict)]
    if len(ids)!=len(items) or any(type(i) is not int or not 1<=i<=999999999 for i in ids) or len(set(ids))!=len(ids):
        return []
    output=[]
    for row in items:
        try:
            nav_day=date.fromisoformat(row["nav_date"])
            metadata_day=date.fromisoformat(row["amfi_metadata_date"])
            nav_age=(today-nav_day).days
            if (not 0<=nav_age<=7 or not 0<=(today-metadata_day).days<=7
                or row["nav_date"]!=historical.get("comparison_date") or metadata_day!=nav_day
                or row.get("amfi_plan")!="DIRECT" or row.get("amfi_option")!="GROWTH"
                or not isinstance(row.get("category"),str) or not row["category"].lower().strip().endswith(" - "+label+")")
                or not isinstance(row.get("isin_growth"),str) or not re.fullmatch(r"IN[A-Z0-9]{10}",row["isin_growth"])
                or not isinstance(row.get("scheme_name"),str) or not row["scheme_name"].strip()
                or type(row.get("observations")) is not int or row["observations"]<650
                or not isinstance(row.get("sources"),list) or "AMFI" not in row["sources"]
                or any(source not in ("AMFI","MFAPI") for source in row["sources"])):
                continue
            nav=Decimal(str(row["nav"]))
            if not nav.is_finite() or not 0<nav<=Decimal("1000000000"):
                continue
            def metric(key,lower=None,upper=None):
                x=row.get(key)
                if type(x) not in (int,float) or not isfinite(x):
                    return None
                return x if (lower is None or x>=lower) and (upper is None or x<=upper) else None
            output.append(FundEvidence(identifier=str(row["scheme_code"]),name=row["scheme_name"],category=category,
                category_verified=True,plan="DIRECT",option="GROWTH",passive=category=="INDEX",
                nav=nav,nav_date=row["nav_date"],nav_age_days=nav_age,history_years=3,
                returns_1y=metric("cagr_1y_percent",-100),returns_3y=metric("cagr_3y_percent",-100),
                peer_percentile=metric("sample_peer_percentile",0,100) if category in COMPARABLE else None,
                worst_rolling_return=metric("worst_rolling_52w_annualized_percent",-100),
                max_drawdown=metric("drawdown_3y_percent",-100,0),volatility=metric("weekly_volatility_percent",0)))
        except (TypeError,ValueError,KeyError,InvalidOperation,OverflowError):
            continue
    return output


def _rolling_peer_context(row):
    block=row.get("rolling_peer_consistency")
    if not isinstance(block,dict) or block.get("status")!="MATCHED_SAMPLE_ONLY":
        return None
    keys=("matched_windows","total_windows","minimum_peer_count","above_median_windows","below_median_windows","tied_windows")
    if any(type(block.get(k)) is not int or block[k]<0 for k in keys):
        return None
    matched=block["matched_windows"]
    if not (block["total_windows"]==105 and 84<=matched<=105 and 4<=block["minimum_peer_count"]<=39
            and sum(block[k] for k in keys[-3:])==matched):
        return None
    for k in ("above_median_percent","median_difference_pp","worst_difference_pp"):
        if type(block.get(k)) not in (int,float) or not isfinite(block[k]):
            return None
    if abs(block["above_median_percent"]-100*block["above_median_windows"]/matched)>.0001 or block["worst_difference_pp"]>block["median_difference_pp"]:
        return None
    return {"status":"MATCHED_SAMPLE_ONLY",**{k:block[k] for k in (*keys,"above_median_percent","median_difference_pp","worst_difference_pp")},
            "notice":"Overlapping matched NAV windows versus the other sampled funds, not official benchmark TRI or independent observations."}


def _unique_match(rows,identifier):
    matches=[r for r in rows if isinstance(r,dict) and r.get("scheme_code")==identifier]
    return matches[0] if len(matches)==1 else {}


def _fund_assessment(fund,source,disclosure,portfolio,top,growth,fit):
    """Descriptive findings, never a substitute for the two qualification gates.

    All inputs originate from existing local read models. Review thresholds are
    explicit research prompts, not a calibrated risk score or category mandate.
    """
    supporting=[]
    review=[]
    gaps=set(top["missing"])|set(growth["missing"])
    def finding(target,code,value,unit,source):
        target.append({"code":code,"value":value,"unit":unit,"source":source})
    def weight(value):
        return type(value) in (int,float) and _bounded(value,0,100.5)
    if _bounded(fund.returns_3y,-100) and fund.returns_3y>0:
        finding(supporting,"POSITIVE_REPORTED_THREE_YEAR_CAGR",fund.returns_3y,"PERCENT","NAV_HISTORY")
    if _bounded(fund.worst_rolling_return,-100) and fund.worst_rolling_return<0:
        finding(review,"NEGATIVE_WORST_ROLLING_YEAR",fund.worst_rolling_return,"PERCENT","NAV_HISTORY")
    rolling=_rolling_peer_context(source) if fund.category in COMPARABLE else None
    if rolling:
        n=rolling["matched_windows"]
        if rolling["above_median_windows"]>n/2 and rolling["median_difference_pp"]>0:
            finding(supporting,"ABOVE_PEER_MEDIAN_IN_MAJORITY_OF_MATCHED_WINDOWS",rolling["above_median_percent"],"PERCENT","MATCHED_NAV_PEER_SAMPLE")
        elif rolling["below_median_windows"]>n/2 and rolling["median_difference_pp"]<0:
            finding(review,"BELOW_PEER_MEDIAN_IN_MAJORITY_OF_MATCHED_WINDOWS",
                    round(100*rolling["below_median_windows"]/n,4),"PERCENT","MATCHED_NAV_PEER_SAMPLE")
    elif fund.category in COMPARABLE:
        gaps.add("MATCHED_ROLLING_PEER_EVIDENCE_REQUIRED")
    if not disclosure:
        gaps.add("MATCHED_SECONDARY_DISCLOSURE_REQUIRED")
    else:
        if disclosure.get("conflicts"):
            finding(review,"REPORTED_DISCLOSURE_CONFLICTS_REQUIRE_REVIEW",None,None,"SECONDARY_DISCLOSURE")
        if disclosure.get("riskometer") in ("HIGH","VERY_HIGH") and fit.get("risk_tolerance")=="LOW":
            finding(review,"REPORTED_HIGH_RISKOMETER_REVIEW_FOR_LOW_RISK_TOLERANCE",None,None,"SECONDARY_DISCLOSURE")
    if not portfolio or portfolio.get("status")!="SECONDARY_COMPOSITION_ONLY":
        gaps.add("MATCHED_REPORTED_PORTFOLIO_REQUIRED")
    else:
        underlying=portfolio.get("underlying_research") or {}
        multi=underlying.get("multi_year_quality") or {}
        exact=portfolio.get("exact_listed_equity_weight_percent")
        assessed=multi.get("assessed_weight_percent")
        flagged=multi.get("review_weight_percent")
        if (multi.get("status")=="REPORTED_MULTI_YEAR_EXPOSURE" and all(weight(v) for v in (exact,assessed,flagged))
                and 0<assessed<=exact and flagged<=assessed):
            if flagged>0:
                finding(review,"REPORTED_MULTI_YEAR_BUSINESS_REVIEW_EXPOSURE",flagged,"FUND_WEIGHT_PERCENT","REPORTED_PORTFOLIO_AND_COMPANY_HISTORY")
            if exact-assessed>.0001:
                gaps.add("PARTIAL_MULTI_YEAR_COMPANY_COVERAGE")
        elif fund.category in COMPARABLE:
            gaps.add("MATCHED_MULTI_YEAR_COMPANY_EVIDENCE_REQUIRED")
        concentration=portfolio.get("concentration_research") or {}
        if concentration.get("category")==fund.category:
            gaps.update(g for g in concentration.get("missing_risk_evidence",[])
                        if isinstance(g,str) and re.fullmatch(r"[A-Z_]{1,100}",g))
            if concentration.get("status")=="EXACT_EQUITY_SUBSET_ONLY":
                total=concentration.get("exact_equity_weight_percent")
                if weight(total) and total==exact:
                    largest=concentration.get("largest_equity_weight_percent")
                    sector=concentration.get("largest_classified_sector_weight_percent")
                    classified=concentration.get("sector_classified_weight_percent")
                    if weight(largest) and 10<=largest<=total:
                        finding(review,"LARGEST_EXACT_EQUITY_AT_LEAST_TEN_PERCENT",largest,"FUND_WEIGHT_PERCENT","REPORTED_PORTFOLIO")
                    if weight(sector) and weight(classified) and 30<=sector<=classified<=total:
                        finding(review,"CLASSIFIED_SECTOR_AT_LEAST_THIRTY_PERCENT",sector,"FUND_WEIGHT_PERCENT","REPORTED_PORTFOLIO_AND_COMPANY_PROFILES")
        if underlying.get("relative_valuation"):
            gaps.add("DATED_UNDERLYING_VALUATION_EVIDENCE_REQUIRED")
    if fit.get("status")=="POOR_FIT":
        finding(review,"SELECTED_HORIZON_OR_RISK_REQUIRES_REVIEW",None,None,"SUITABILITY")
    return {"version":"FUND-ASSESSMENT-1","status":"REVIEW_REQUIRED" if review else "DESCRIPTIVE_EVIDENCE_ONLY",
            "supporting_evidence":supporting,"review_findings":review,"next_evidence_checks":sorted(gaps),
            "notice":"Historical and secondary reported observations only. The 10% holding and 30% sector review thresholds are descriptive prompts, not regulatory limits or calibrated risks. No predicted return, fund rating or qualification change."}


def _research_reports(candidates, ranked, source_rows, disclosed, portfolios):
    """Build bounded, deterministic reports from the same exact-scheme evidence
    and qualification decisions used by the existing recommendation endpoint.
    Secondary evidence is descriptive and never substitutes for missing gates.
    """
    if not candidates:
        return []
    exclusions={row["identifier"]:row for row in ranked["excluded"]}
    top_ranks={row["fund"]["identifier"]:row["rank"] for row in ranked["top_performers"]}
    growth_ranks={row["fund"]["identifier"]:row["rank"] for row in ranked["growth_outlook"]}
    sources={str(row["scheme_code"]):row["sources"] for row in source_rows
             if isinstance(row,dict) and type(row.get("scheme_code")) is int and isinstance(row.get("sources"),list)}
    source_by_id={str(row["scheme_code"]):row for row in source_rows if isinstance(row,dict) and type(row.get("scheme_code")) is int}
    disclosure_ids={row["scheme_code"] for row in disclosed}
    portfolio_ids={row["scheme_code"] for row in portfolios}
    reports=[]
    for fund in sorted(candidates,key=lambda f:f.identifier):
        missing=exclusions.get(fund.identifier,{})
        top_missing=missing.get("top_performer_missing",[])
        growth_missing=missing.get("growth_outlook_missing",[])
        def decision(blockers,ranks):
            return {"status":"WITHHELD" if blockers else "QUALIFIED",
                    "missing":blockers,"published_rank":ranks.get(fund.identifier)}
        top=decision(top_missing,top_ranks)
        growth=decision(growth_missing,growth_ranks)
        reports.append({
            "identifier":fund.identifier,"name":fund.name,"category":fund.category,
            "plan":fund.plan,"option":fund.option,"nav":str(fund.nav) if fund.nav is not None else None,
            "nav_date":fund.nav_date,"nav_age_days":fund.nav_age_days,
            "historical":{"sources":sources.get(fund.identifier,[]),
                "returns_1y":fund.returns_1y,"returns_3y":fund.returns_3y,
                "sample_peer_percentile":fund.peer_percentile,"worst_rolling_return":fund.worst_rolling_return,
                "max_drawdown":fund.max_drawdown,"volatility":fund.volatility,
                "rolling_peer_consistency":_rolling_peer_context(source_by_id.get(fund.identifier,{})) if fund.category in COMPARABLE else None},
            "research_assessment":_fund_assessment(fund,source_by_id.get(fund.identifier,{}),
                _unique_match(disclosed,fund.identifier),_unique_match(portfolios,fund.identifier),top,growth,ranked["suitability"]),
            "secondary_disclosure_available":fund.identifier in disclosure_ids,
            "secondary_portfolio_available":fund.identifier in portfolio_ids,
            "top_performer":top,"growth_outlook":growth,
            "suitability":ranked["suitability"],
            "conclusion":"Evidence gates met for both research lists." if not top_missing and not growth_missing
                else "Neither research list qualifies; review the available research evidence." if top_missing and growth_missing
                else "Only one research list meets its evidence gates; review the separate decisions.",
            "reassessment":"Re-evaluate when missing dated evidence is acquired or suitability changes. Historical returns are not a forecast."
        })
    return reports


def _history_gate_counts(historical):
    counts=historical.get("history_gate_counts")
    keys=("OFFICIAL_ANCHOR_UNAVAILABLE","COMPARISON_DATE_MISMATCH","HISTORY_QUALITY_OR_LENGTH","ELIGIBLE")
    sample=historical.get("sample_count")
    if (not isinstance(counts,dict) or set(counts)!=set(keys)
        or type(sample) is not int or not 0<=sample<=40
        or any(type(counts[k]) is not int or counts[k]<0 for k in keys)
        or sum(counts.values())!=sample or counts["ELIGIBLE"]!=historical.get("eligible_count")):
        return None
    return {k:counts[k] for k in keys}


def dashboard(category:str="LARGE_CAP",horizon_months:int=60,risk_tolerance:str="MODERATE"):
    if category not in CATEGORIES:raise ValueError("UNSUPPORTED_CATEGORY")
    if horizon_months<12 or horizon_months>360:raise ValueError("INVALID_HORIZON")
    if risk_tolerance not in RISK_LEVELS:raise ValueError("INVALID_RISK_TOLERANCE")
    candidates,coverage=_catalog_candidates(category)
    # AMFI history is independent of the Upstox discovery catalog. Do not
    # equate sampled NAV history with complete benchmark/holdings evidence.
    historical=None
    try:
        observed=backend_json("/api/v1/mutual-funds/historical-watch?category="+category)
        if (isinstance(observed,dict) and observed.get("category")==category
                and type(observed.get("universe_count")) is int
                and type(observed.get("eligible_count")) is int
                and 0<=observed["eligible_count"]<=observed["universe_count"]
                and isinstance(observed.get("items"),list)):
            historical=observed
            coverage["official_category_verified"]=observed["universe_count"]
            coverage["dated_nav_history_eligible"]=observed["eligible_count"]
    except Exception:
        pass  # Local backend unavailability is not permission to fabricate history.
    official=_official_history_candidates(historical,category,datetime.now(ZoneInfo("Asia/Kolkata")).date()) if historical else []
    coverage["explicit_amfi_history_candidates"]=len(official)
    official_ids={f.identifier for f in official}
    # All sampled candidates enter the gates. Secondary diagnostics remain bounded to five.
    source_rows=historical.get("research_candidates",historical["items"]) if historical else []
    disclosed=fund_disclosures.matched([row for row in source_rows if isinstance(row,dict) and str(row.get("scheme_code")) in official_ids],datetime.now(ZoneInfo("Asia/Kolkata")).date()) if official else []
    coverage["secondary_disclosure_matches"]=len(disclosed)
    portfolios=fund_portfolios.matched(disclosed)
    coverage["secondary_portfolio_matches"]=len(portfolios)
    # Public catalog discovery remains separate from exact AMFI scheme evidence.
    # Unknown fee, benchmark, holdings and risk data still block recommendations.
    ranked=rank_candidates(official,category,horizon_months,risk_tolerance)
    blockers=["OFFICIAL_CATEGORY_SOURCE_NOT_CONNECTED","DATED_NAV_HISTORY_INSUFFICIENT",
              "BENCHMARK_TRI_NOT_CONNECTED","OFFICIAL_RISKOMETER_NOT_CONNECTED",
              "PORTFOLIO_DISCLOSURES_NOT_CONNECTED","HOLDING_FUNDAMENTALS_NOT_CONNECTED",
              "EXPENSE_RATIO_NOT_CONNECTED","LICENSED_RATING_SOURCE_NOT_CONNECTED"]
    if historical is not None:
        if coverage["official_category_verified"]>0:
            blockers.remove("OFFICIAL_CATEGORY_SOURCE_NOT_CONNECTED")
        if coverage["dated_nav_history_eligible"]>0:
            blockers.remove("DATED_NAV_HISTORY_INSUFFICIENT")
    else:
        blockers.append("AMFI_HISTORY_READ_MODEL_UNAVAILABLE")
    if category in SPECIALIZED:
        blockers.append("CATEGORY_SPECIFIC_RISK_MODEL_REQUIRED")
    generated=datetime.now(timezone.utc).isoformat()
    payload={"generated_at":generated,"methodology_version":METHODOLOGY_VERSION,"category":category,
      "filters":{"horizon_months":horizon_months,"risk_tolerance":risk_tolerance},"coverage":coverage,
      "top_performers":ranked["top_performers"],"growth_outlook":ranked["growth_outlook"],
      "portfolio_overlap":fund_portfolios.overlap(disclosed),
      "research_reports":_research_reports(official,ranked,source_rows,disclosed,portfolios),
      "portfolio_evidence":{"status":"SECONDARY_COMPOSITION_ONLY" if portfolios else "NOT_AVAILABLE_OR_NOT_AUTHORIZED",
          "items":portfolios,"notice":"Selected fund coverage only. Reported weights and existing cached company evidence are not verified forward earnings or valuation coverage."},
      "disclosure_evidence":{"status":"SECONDARY_REPORTED" if disclosed else "NOT_AVAILABLE_OR_NOT_AUTHORIZED",
          "items":disclosed,"notice":"AMFI-derived disclosures from TigZig, not independently verified. AUM covers all plans; dates differ by field. Reported benchmark names are not benchmark return histories. No holdings or rating verification."},
      "historical_coverage":{"status":"UNAVAILABLE"} if historical is None else {
          "status":historical.get("status"),"comparison_date":historical.get("comparison_date"),
          "universe_count":historical["universe_count"],"eligible_count":historical["eligible_count"],
          "sample_count":historical.get("sample_count"),"history_gate_counts":_history_gate_counts(historical),
          "weekly_risk_eligible_count":historical.get("weekly_risk_eligible_count"),
          "items":historical["items"][:5]},
      "suitability":ranked["suitability"],"blockers":blockers,
      "qualification_summary":{"evaluated_count":len(official),"top_eligible_count":ranked["top_eligible_count"],
          "growth_eligible_count":ranked["growth_eligible_count"],"excluded":ranked["excluded"]},
      "market_overview":[{"segment":x,"status":"UNAVAILABLE","benchmark":None,"period":None,
                          "last_available_date":None,"evidence":[],"blocker":"BENCHMARK_TRI_NOT_CONNECTED"}
                         for x in ("LARGE_CAP","MID_CAP","SMALL_CAP")],
      "recommendation_status":"QUALIFIED_RESEARCH_AVAILABLE" if ranked["top_performers"] or ranked["growth_outlook"] else "NO_QUALIFYING_FUNDS_INCOMPLETE_EVIDENCE",
      "notice":"Discovery records are not recommendations. Top Performer and Growth Outlook use independent evidence gates; zero picks is allowed."}
    # The observation timestamp is metadata, not research evidence. Excluding it
    # keeps identical results idempotent and gives alerts a stable dedupe key.
    stable_payload={key:value for key,value in payload.items() if key!="generated_at"}
    digest=hashlib.sha256(json.dumps(stable_payload,sort_keys=True,default=str).encode()).hexdigest()
    payload["snapshot_hash"]=digest
    with nav_catalog._LOCK,nav_catalog._connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS mf_recommendation_snapshots(
          snapshot_hash TEXT PRIMARY KEY,generated_at TEXT NOT NULL,methodology_version TEXT NOT NULL,
          category TEXT NOT NULL,horizon_months INTEGER NOT NULL,risk_tolerance TEXT NOT NULL,result_json TEXT NOT NULL)""")
        db.execute("INSERT OR IGNORE INTO mf_recommendation_snapshots VALUES(?,?,?,?,?,?,?)",
          (digest,generated,METHODOLOGY_VERSION,category,horizon_months,risk_tolerance,json.dumps(payload,default=str,separators=(",",":"))))
        db.commit()
    return payload
