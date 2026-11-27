"""Fund-weighted dated business drivers, not a forward EPS or NAV forecast."""
from collections import defaultdict
from datetime import datetime,timedelta
from math import isfinite
import re
from zoneinfo import ZoneInfo
from . import quarterly_financials

VERSION="MF-QUARTERLY-DRIVERS-1"
NOTICE=("Original reported fund weights and exact fiscal quarter cohorts. Weighted growth is a descriptive mean "
        "of covered company rates, not aggregate earnings growth or predicted fund return. "
        "Negative bases withhold growth; different fiscal periods remain separate. Unverified holdings and "
        "provider statements cannot establish forecast earnings, fair value or qualified Growth Outlook.")
def num(v):return type(v) in (int,float) and isfinite(v)

def summarize(equities,reports,instant):
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    out={"methodology":VERSION,"status":"AWAITING_QUARTERLY_EVIDENCE","exact_weight_percent":None,
         "assessed_weight_percent":0,"review_weight_percent":0,"unassessed_weight_percent":100,
         "quarter_cohorts":[],"forward_earnings_coverage_percent":None,"forecast_nav_return_percent":None,"notice":NOTICE}
    seen=set();exact=0
    for h in equities:
        isin,w=h.get("isin"),h.get("weight_percent")
        if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or isin in seen or not num(w) or not 0<w<=100:
            return {**out,"status":"INVALID_HOLDING_IDENTITIES"}
        seen.add(isin);exact+=w
    if exact>100.5:return {**out,"status":"INVALID_HOLDING_IDENTITIES"}
    cohorts=defaultdict(lambda:{"assessed":0.,"review":0.,"joint_coverage":0.,"joint_growth":0.,"joint_acceleration":0.,
        "joint_acceleration_coverage":0.,"profit_loss":0.,"metrics":{}})
    assessed=flagged=0.
    for h in equities:
        isin,w=h["isin"],h["weight_percent"]
        raw=reports.get(isin)
        if not isinstance(raw,dict) or raw.get("isin")!=isin or raw.get("historical_cache_only") is True:continue
        try:
            stamp=datetime.fromisoformat(raw["retrieved_at"])
            if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant:continue
            q=quarterly_financials.summarize(raw,today)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):continue
        if q.get("status") not in ("REPORTED_QUARTERLY_COMPARISONS","PARTIAL_LATEST_QUARTER"):continue
        rows={r["metric"]:r for r in q["items"]}
        if not rows:continue
        bucket=cohorts[q["latest_period"]]
        assessed+=w;bucket["assessed"]+=w
        review=False
        for key,row in rows.items():
            m=bucket["metrics"].setdefault(key,{"amount_coverage":0.,"negative_amount":0.,"yoy_coverage":0.,
                "positive_yoy":0.,"negative_yoy":0.,"flat_yoy":0.,"sum_yoy":0.,
                "acceleration_coverage":0.,"accelerating":0.,"decelerating":0.,"flat_acceleration":0.})
            latest=row["latest_value"];yoy=row["year_over_year_growth_percent"];acc=row["growth_acceleration_pp"]
            m["amount_coverage"]+=w
            if latest<0:m["negative_amount"]+=w;review=True
            if num(yoy):
                m["yoy_coverage"]+=w;m["sum_yoy"]+=w*yoy
                m["positive_yoy" if yoy>0 else "negative_yoy" if yoy<0 else "flat_yoy"]+=w
                review=review or yoy<0
            if num(acc):
                m["acceleration_coverage"]+=w
                m["accelerating" if acc>0 else "decelerating" if acc<0 else "flat_acceleration"]+=w
                review=review or acc<0
        revenue,profit=rows.get("revenue",{}),rows.get("net_profit",{})
        if num(profit.get("latest_value")) and profit["latest_value"]<0:bucket["profit_loss"]+=w
        a,b=revenue.get("year_over_year_growth_percent"),profit.get("year_over_year_growth_percent")
        if num(a) and num(b):
            bucket["joint_coverage"]+=w
            if a>0 and b>0:bucket["joint_growth"]+=w
        a,b=revenue.get("growth_acceleration_pp"),profit.get("growth_acceleration_pp")
        if num(a) and num(b):
            bucket["joint_acceleration_coverage"]+=w
            if a>0 and b>0:bucket["joint_acceleration"]+=w
        if review:flagged+=w;bucket["review"]+=w
    def rd(v):return round(v,4)
    for period,b in sorted(cohorts.items(),reverse=True):
        metrics=[]
        for key,m in sorted(b["metrics"].items()):
            metrics.append({"metric":key,**{k+"_weight_percent":rd(v) for k,v in m.items() if k!="sum_yoy"},
              "covered_subset_weighted_yoy_percent":rd(m["sum_yoy"]/m["yoy_coverage"]) if m["yoy_coverage"] else None})
        out["quarter_cohorts"].append({"period":period,**{k+"_weight_percent":rd(v) for k,v in b.items() if k!="metrics"},"metrics":metrics})
    out.update(status="REPORTED_QUARTERLY_DRIVERS_ONLY" if assessed else "AWAITING_QUARTERLY_EVIDENCE",
        exact_weight_percent=rd(exact),assessed_weight_percent=rd(assessed),review_weight_percent=rd(flagged),
        unassessed_weight_percent=rd(max(0,100-assessed)))
    return out

def readiness(category,reports,portfolios,today):
    """Separate driver review from historical NAV selection and final growth gates."""
    from .fund_categories import COMPARABLE
    out={"methodology":VERSION,"status":"AWAITING_MATCHED_DRIVERS","items":[],"notice":NOTICE}
    if category not in COMPARABLE:
        out["status"]="CATEGORY_SPECIFIC_MODEL_REQUIRED";return out
    indexed=defaultdict(list)
    for r in reports:indexed[r.get("identifier")].append(r)
    seen=set()
    for p in portfolios:
        code=p.get("scheme_code");r=indexed.get(code,[])
        if code in seen or len(r)!=1 or r[0].get("category")!=category or r[0].get("plan")!="DIRECT" or r[0].get("option")!="GROWTH":continue
        if p.get("status")!="SECONDARY_COMPOSITION_ONLY":continue
        try:
            from datetime import date
            if not 0<=(today-date.fromisoformat(p["portfolio_date"])).days<=60 or not 0<=(today-date.fromisoformat(r[0]["nav_date"])).days<=7:continue
        except (ValueError,TypeError,KeyError):continue
        q=(p.get("underlying_research") or {}).get("quarterly_growth_drivers") or {}
        if q.get("methodology")!=VERSION or q.get("status")!="REPORTED_QUARTERLY_DRIVERS_ONLY":continue
        # Never merge different fiscal periods, or extrapolate from a researched subset.
        candidates=[c for c in q.get("quarter_cohorts",[]) if num(c.get("joint_coverage_weight_percent")) and c["joint_coverage_weight_percent"]>=70]
        if len(candidates)!=1:continue
        c=candidates[0];coverage=c["joint_coverage_weight_percent"];growth=c.get("joint_growth_weight_percent");review=c.get("review_weight_percent")
        if not all(num(v) for v in (growth,review)) or not 0<=growth<=coverage<=100.5 or not 0<=review<=100.5:continue
        seen.add(code)
        out["items"].append({"identifier":code,"name":r[0].get("name"),"portfolio_date":p["portfolio_date"],
            "quarter":c["period"],"joint_coverage_weight_percent":coverage,"joint_growth_weight_percent":growth,
            "review_weight_percent":review,"state":"DRIVER_REVIEW_REQUIRED" if review>20 or growth<50 else "POSITIVE_HISTORICAL_DRIVERS_ONLY",
            "qualified":False,"forecast_return_percent":None,"blockers":["INDEPENDENT_OFFICIAL_HOLDINGS_REQUIRED",
              "DATED_FORWARD_EARNINGS_ESTIMATES_REQUIRED","DATED_INTRINSIC_VALUATION_REQUIRED","PROSPECTIVE_GROWTH_VALIDATION_REQUIRED"]})
    out["items"].sort(key=lambda r:r["identifier"])
    if out["items"]:out["status"]="MATCHED_HISTORICAL_DRIVERS"
    return out
