"""Bounded exact-date historical peer research, separate from qualified fund lists.

No estimated future performance, benchmark TRI substitution or official rating.
"""
from collections import Counter,defaultdict
from datetime import date
from math import isfinite
from statistics import median
import re
from .fund_categories import COMPARABLE

VERSION="MF-MATCHED-PEER-1"
NOTICE=("Direct Growth schemes in the same AMFI category and exact 157 observed weekly NAV dates. "
        "Four equally weighted peer midrank percentiles: annualized return, worst rolling year, lower weekly "
        "drawdown and lower annualized volatility. Minimum five schemes in a matched local cohort. "
        "Provisional historical research prioritization, not a fund rating, future return, official benchmark TRI, "
        "market-wide ranking or investment recommendation. Risk bands describe relative observed price risk only. "
        "Missing official fee, Riskometer, benchmark and forward evidence still block qualified lists.")
FACTORS=("cagr","worst_rolling","drawdown","lower_volatility")
def num(x,lo,hi):
    return type(x) in (float,int) and isfinite(x) and lo<=x<=hi
def percentile(value,values):
    return 100*(sum(v<value for v in values)+.5*(sum(v==value for v in values)-1))/(len(values)-1)
def build(candidates,source_rows,category,fit,today,rolling_context):
    report={"methodology":VERSION,"status":"AWAITING_MATCHED_HISTORY","category":category,"eligible_count":0,
        "matched_count":0,"cohort_count":0,"items":[],"notice":NOTICE}
    if category not in COMPARABLE:
        report["status"]="CATEGORY_SPECIFIC_MODEL_REQUIRED";return report
    if fit.get("status")!="POTENTIALLY_SUITABLE":
        report["status"]="SELECTED_HORIZON_OR_RISK_REVIEW";return report
    if not isinstance(source_rows,list) or len(source_rows)>40 or len(candidates)>40:return report
    ids=Counter(str(r.get("scheme_code")) for r in source_rows if isinstance(r,dict))
    isins=Counter(r.get("isin_growth") for r in source_rows if isinstance(r,dict) and isinstance(r.get("isin_growth"),str))
    source={str(r["scheme_code"]):r for r in source_rows if isinstance(r,dict) and type(r.get("scheme_code")) is int}
    cohorts=defaultdict(list)
    for f in candidates:
        r=source.get(f.identifier,{})
        isin=r.get("isin_growth");w=r.get("matched_weekly_comparison")
        if f.category!=category or f.category_verified is not True or f.plan!="DIRECT" or f.option!="GROWTH" or ids[f.identifier]!=1 or not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin) or isins[isin]!=1:continue
        if not isinstance(w,dict) or w.get("methodology")!="MF-WEEKLY-MATCH-1" or w.get("anchor_count")!=157 or not isinstance(w.get("date_digest"),str) or not re.fullmatch(r"[a-f0-9]{64}",w["date_digest"]):continue
        try:
            first,last=date.fromisoformat(w["first_date"]),date.fromisoformat(w["last_date"])
            if not 1092<=(last-first).days<=1095 or w["last_date"]!=f.nav_date or not 0<=(today-last).days<=7:continue
        except (ValueError,TypeError,KeyError):continue
        rolling=rolling_context(r)
        if not rolling or not num(rolling.get("above_median_percent"),0,100) or not num(w.get("cagr_percent"),-100,1e6) or not num(w.get("drawdown_percent"),-100,0) or not num(f.worst_rolling_return,-100,1e6) or not num(f.volatility,0,1e6):continue
        values=(w["cagr_percent"],f.worst_rolling_return,w["drawdown_percent"],-f.volatility)
        cohorts[(w["first_date"],w["last_date"],w["date_digest"])].append((f,isin,values,rolling))
        report["eligible_count"]+=1
    # A single largest exact-date cohort: do not compare percentiles across
    # different anchor schedules or pick a cohort based on performance.
    viable=[(k,v) for k,v in cohorts.items() if len(v)>=5]
    report["cohort_count"]=len(viable)
    if not viable:return report
    key,rows=min(viable,key=lambda kv:(-len(kv[1]),kv[0]))
    columns=list(zip(*(r[2] for r in rows)))
    vol_median=median(-v for v in columns[3]);dd_median=median(-v for v in columns[2])
    output=[]
    for f,isin,values,rolling in rows:
        points={k:round(percentile(v,c),4) for k,v,c in zip(FACTORS,values,columns)}
        score=round(sum(points.values())/len(points),4)
        risk="ABOVE_PEER_MEDIAN_DOWNSIDE" if -values[2]>dd_median or -values[3]>vol_median else "AT_OR_BELOW_PEER_MEDIAN_DOWNSIDE"
        # A fund must exhibit positive multi-year return and at least median
        # score. Don't fill five slots with weak performers or unsuitable funds.
        if values[0]<=0 or score<50:continue
        output.append({"identifier":f.identifier,"name":f.name,"isin_growth":isin,"nav":str(f.nav),"nav_date":f.nav_date,
            "score":score,"components":points,"weekly_cagr_percent":values[0],"worst_rolling_year_percent":values[1],
            "weekly_drawdown_percent":values[2],"annualized_volatility_percent":-values[3],
            "rolling_peer_above_median_percent":rolling["above_median_percent"],"relative_risk":risk,
            "status":"HISTORICAL_RESEARCH_ONLY","qualified":False})
    output.sort(key=lambda r:(-r["score"],r["identifier"]))
    report.update(status="HISTORICAL_SHORTLIST_AVAILABLE" if output else "NO_HISTORICAL_MATCHES",
        matched_count=len(rows),first_date=key[0],last_date=key[1],date_digest=key[2],
        median_weekly_cagr_percent=round(median(columns[0]),4),median_weekly_drawdown_percent=round(-dd_median,4),
        median_annualized_volatility_percent=round(vol_median,4),items=output[:5])
    return report

QUALITY_NOTICE=("Historical company evidence for current reported fund holdings only, not fund earnings growth or a "
                "forward NAV projection. Uses original fund weights, never fills unassessed exposure or substitutes "
                "undated valuations. Fixed review thresholds are illustrative; secondary holdings are not independently verified.")
def quality_watch(candidates,portfolios,category,fit,today):
    report={"status":"AWAITING_MATCHED_PORTFOLIO_EVIDENCE","evaluated_count":0,"items":[],"notice":QUALITY_NOTICE}
    if category not in COMPARABLE:
        report["status"]="CATEGORY_SPECIFIC_MODEL_REQUIRED";return report
    if fit.get("status")!="POTENTIALLY_SUITABLE":
        report["status"]="SELECTED_HORIZON_OR_RISK_REVIEW";return report
    if not isinstance(portfolios,list) or len(portfolios)>40:return report
    funds={f.identifier:f for f in candidates if f.category==category and f.category_verified is True}
    counts=Counter(p.get("scheme_code") for p in portfolios if isinstance(p,dict))
    for p in portfolios:
        if not isinstance(p,dict):continue
        code=p.get("scheme_code");f=funds.get(code) if isinstance(code,str) else None
        if not f or counts[code]!=1 or p.get("status")!="SECONDARY_COMPOSITION_ONLY" or f.plan!="DIRECT" or f.option!="GROWTH":continue
        try:
            day=date.fromisoformat(p["portfolio_date"])
            if not 0<=(today-day).days<=60:continue
        except (ValueError,TypeError,KeyError):continue
        u=p.get("underlying_research") or {};multi=u.get("multi_year_quality") or {}
        exact=p.get("exact_listed_equity_weight_percent");assessed=multi.get("assessed_weight_percent");review=multi.get("review_weight_percent")
        if multi.get("status")!="REPORTED_MULTI_YEAR_EXPOSURE" or not all(num(x,0,100.5) for x in (exact,assessed,review)) or not 0<=review<=assessed<=exact:continue
        report["evaluated_count"]+=1
        # Require 70% original fund weight with same four-year profit history.
        # Never sum different fiscal periods or renormalize missing weights.
        rows=[r for r in multi.get("historical_growth",[]) if isinstance(r,dict) and r.get("metric")=="NET_PROFIT"]
        valid=[]
        for r in rows:
            periods=r.get("periods");coverage=r.get("coverage_weight_percent");positive=r.get("positive_growth_weight_percent");negative=r.get("negative_growth_weight_percent");flat=r.get("flat_growth_weight_percent")
            if not isinstance(periods,list) or len(periods)!=4 or any(not isinstance(v,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",v) for v in periods):continue
            try:
                ds=[date.fromisoformat(v) for v in periods]
                if any(b.year-a.year!=1 or a.month!=b.month for a,b in zip(ds,ds[1:])) or not 0<=(today-ds[-1]).days<=550:continue
            except ValueError:continue
            if not all(num(x,0,100.5) for x in (coverage,positive,negative,flat)) or not 70<=coverage<=assessed or abs(positive+negative+flat-coverage)>.01 or positive<50 or review>20:continue
            if not num(r.get("covered_subset_weighted_cagr_percent"),0,1e6):continue
            valid.append(r)
        if len(valid)!=1:continue
        r=valid[0]
        report["items"].append({"identifier":code,"name":f.name,"portfolio_date":p["portfolio_date"],"periods":r["periods"],
            "profit_history_weight_percent":r["coverage_weight_percent"],"positive_profit_growth_weight_percent":r["positive_growth_weight_percent"],
            "review_weight_percent":review,"unassessed_fund_weight_percent":round(max(0,100-assessed),4),
            "covered_company_profit_cagr_percent":r["covered_subset_weighted_cagr_percent"],
            "status":"HISTORICAL_HOLDINGS_REVIEW_ONLY","qualified":False})
    # No cross-period performance ranking; deterministic report navigation.
    report["items"].sort(key=lambda r:r["identifier"])
    report["items"]=report["items"][:5]
    if report["items"]:report["status"]="HISTORICAL_HOLDINGS_MATCHES"
    return report
