"""Deterministic, fail-closed mutual-fund research rankings.

The connected catalog is useful for discovery but is not silently promoted into
recommendations. Rankings require dated, source-attributed evidence.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

from . import nav_catalog

METHODOLOGY_VERSION = "MF-RESEARCH-1.0.0"
CATEGORIES = ("LARGE_CAP","MID_CAP","SMALL_CAP","FLEXI_CAP","INDEX")
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
        return None
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
    if horizon_months<=36:
        flags.append("POOR_FIT_FOR_36_MONTH_GOAL")
    elif horizon_months<60:
        flags.append("SHORT_HORIZON_FOR_EQUITY")
    if risk_tolerance=="LOW" and category in {"MID_CAP","SMALL_CAP"}:
        flags.append("ABOVE_SELECTED_RISK_TOLERANCE")
    elif risk_tolerance=="MODERATE" and category=="SMALL_CAP":
        flags.append("ABOVE_SELECTED_RISK_TOLERANCE")
    return {"status":"POOR_FIT" if flags else "POTENTIALLY_SUITABLE",
            "flags":flags,"horizon_months":horizon_months,"risk_tolerance":risk_tolerance}

def _missing_top(f:FundEvidence):
    missing=[]
    if not f.category_verified:missing.append("OFFICIAL_CATEGORY")
    if f.plan!="DIRECT" or f.option!="GROWTH":missing.append("EXACT_DIRECT_GROWTH_PLAN")
    if f.nav is None or f.nav_date is None or f.nav_age_days is None or f.nav_age_days>7:missing.append("FRESH_DATED_NAV")
    if f.riskometer is None or f.riskometer_date is None:missing.append("OFFICIAL_RISKOMETER")
    if f.history_years<3:missing.append("THREE_YEAR_NAV_HISTORY")
    if f.expense_ratio is None:missing.append("EXPENSE_RATIO")
    if f.passive:
        if not f.benchmark:missing.append("UNDERLYING_INDEX")
        if f.tracking_difference is None:missing.append("TRACKING_DIFFERENCE")
        if f.tracking_error is None:missing.append("TRACKING_ERROR")
    else:
        for value,label in ((f.returns_1y,"ONE_YEAR_RETURN"),(f.returns_3y,"THREE_YEAR_RETURN"),
                            (f.peer_percentile,"PEER_PERCENTILE"),(f.benchmark_hit_rate,"BENCHMARK_HIT_RATE"),
                            (f.worst_rolling_return,"WORST_ROLLING_RETURN"),(f.max_drawdown,"MAX_DRAWDOWN"),
                            (f.volatility,"VOLATILITY")):
            if value is None:missing.append(label)
    return missing

def _missing_growth(f:FundEvidence):
    missing=[]
    if not f.category_verified:missing.append("OFFICIAL_CATEGORY")
    if f.plan!="DIRECT" or f.option!="GROWTH":missing.append("EXACT_DIRECT_GROWTH_PLAN")
    if f.portfolio_age_days is None or f.portfolio_age_days>60:missing.append("RECENT_PORTFOLIO_DISCLOSURE")
    if (f.portfolio_coverage or 0)<.8:missing.append("PORTFOLIO_COVERAGE_80_PERCENT")
    if f.passive:
        if not f.benchmark:missing.append("UNDERLYING_INDEX")
        if (f.index_outlook_coverage or 0)<.7:missing.append("INDEX_OUTLOOK_COVERAGE_70_PERCENT")
        if f.tracking_difference is None:missing.append("TRACKING_DIFFERENCE")
    else:
        if (f.earnings_coverage or 0)<.7:missing.append("EARNINGS_COVERAGE_70_PERCENT")
        if (f.valuation_coverage or 0)<.6:missing.append("VALUATION_COVERAGE_60_PERCENT")
        for value,label in ((f.earnings_growth,"FORWARD_EARNINGS_GROWTH"),
                            (f.valuation_attractiveness,"VALUATION_EVIDENCE"),
                            (f.sector_driver_score,"SECTOR_DRIVERS"),(f.concentration_risk,"CONCENTRATION"),
                            (f.liquidity_score,"LIQUIDITY")):
            if value is None:missing.append(label)
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
    for fund in candidates:
        if fund.category!=category:continue
        top_missing=_missing_top(fund);growth_missing=_missing_growth(fund)
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
    return {"top_performers":top[:5],"growth_outlook":growth[:5],"excluded":excluded,"suitability":fit}

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

def dashboard(category:str="LARGE_CAP",horizon_months:int=60,risk_tolerance:str="MODERATE"):
    if category not in CATEGORIES:raise ValueError("UNSUPPORTED_CATEGORY")
    if horizon_months<12 or horizon_months>360:raise ValueError("INVALID_HORIZON")
    if risk_tolerance not in RISK_LEVELS:raise ValueError("INVALID_RISK_TOLERANCE")
    candidates,coverage=_catalog_candidates(category);ranked=rank_candidates(candidates,category,horizon_months,risk_tolerance)
    blockers=["OFFICIAL_CATEGORY_SOURCE_NOT_CONNECTED","DATED_NAV_HISTORY_INSUFFICIENT",
              "BENCHMARK_TRI_NOT_CONNECTED","OFFICIAL_RISKOMETER_NOT_CONNECTED",
              "PORTFOLIO_DISCLOSURES_NOT_CONNECTED","HOLDING_FUNDAMENTALS_NOT_CONNECTED",
              "EXPENSE_RATIO_NOT_CONNECTED","LICENSED_RATING_SOURCE_NOT_CONNECTED"]
    generated=datetime.now(timezone.utc).isoformat()
    payload={"generated_at":generated,"methodology_version":METHODOLOGY_VERSION,"category":category,
      "filters":{"horizon_months":horizon_months,"risk_tolerance":risk_tolerance},"coverage":coverage,
      "top_performers":ranked["top_performers"],"growth_outlook":ranked["growth_outlook"],
      "suitability":ranked["suitability"],"blockers":blockers,
      "market_overview":[{"segment":x,"status":"UNAVAILABLE","benchmark":None,"period":None,
                          "last_available_date":None,"evidence":[],"blocker":"BENCHMARK_TRI_NOT_CONNECTED"}
                         for x in ("LARGE_CAP","MID_CAP","SMALL_CAP")],
      "recommendation_status":"NO_QUALIFYING_FUNDS_INCOMPLETE_EVIDENCE",
      "notice":"Zero picks is intentional: discovery records are not recommendations. Top Performer and Growth Outlook use independent evidence gates."}
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
