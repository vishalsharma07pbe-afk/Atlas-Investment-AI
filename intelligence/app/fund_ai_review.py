"""Scheduled, public-scheme-only AI claim review using the existing budget/cache."""
from datetime import date
from math import isfinite
import re
from . import automatic_ai_review as ai, fund_growth_drivers
from .fund_categories import COMPARABLE

VERSION="AUTO-FUND-GROUNDED-1"
LIMITS=["Independent official holdings","Dated forward company earnings estimates",
        "Dated intrinsic valuation","Prospective growth validation","No qualified growth recommendation"]
def num(v):return type(v) in (int,float) and isfinite(v)
def fresh(v,today,days):
    try:return 0<=(today-date.fromisoformat(v)).days<=days
    except (ValueError,TypeError):return False
def candidates(snapshot,selected=None):
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return
    try:today=date.fromisoformat(snapshot["research_date"])
    except (ValueError,TypeError,KeyError):return
    for section in snapshot.get("sections",[]):
        cat=section.get("section")
        if cat not in COMPARABLE or section.get("status")!="READY":continue
        result=section.get("result") or {}
        if result.get("category")!=cat:continue
        review=result.get("growth_driver_review") or {}
        if review.get("methodology")!=fund_growth_drivers.VERSION or review.get("status")!="MATCHED_HISTORICAL_DRIVERS":continue
        for row in review.get("items",[])[:5]:
            code=row.get("identifier")
            if not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{5,8}",code) or row.get("qualified") is not False or row.get("forecast_return_percent") is not None:continue
            if not fresh(row.get("portfolio_date"),today,60) or not fresh(row.get("quarter"),today,150) or not fresh(row.get("nav_date"),today,7):continue
            keys=("joint_coverage_weight_percent","joint_growth_weight_percent","review_weight_percent")
            if not all(num(row.get(k)) and 0<=row[k]<=100.5 for k in keys):continue
            if not 70<=row[keys[0]] or row[keys[1]]>row[keys[0]]:continue
            pack={"version":VERSION,"fund":{"scheme_code":code,"category":cat,"portfolio_date":row["portfolio_date"],
                "quarter":row["quarter"],"nav_date":row["nav_date"],**{k:row[k] for k in keys}},"missing":LIMITS}
            yield row,pack,ai.identity(pack,selected)
def attach(snapshot,connect):
    for section in snapshot.get("sections",[]):
        for row in ((section.get("result") or {}).get("growth_driver_review") or {}).get("items",[]):
            if isinstance(row,dict):row.pop("ai_review",None)
    allowed=ai.providers()
    if not allowed:return
    for row,pack,key in candidates(snapshot,allowed):
        cached=ai._read(connect,key)
        if not cached or cached[1] not in ("COMPLETE","PARTIAL","PENDING_MEMBERS","RUNNING"):continue
        result=cached[2]
        reviews=[r for r in result.get("reviews",[]) if r.get("provider") in allowed]
        if reviews:
            row["ai_review"]={"committee":ai._committee(pack,allowed,reviews,set(result.get("attempted_providers",[]))),
               "reviews":reviews,"notice":"Exact supplied public fund observations only; not a forecast or investment decision."}
def refresh(snapshot,connect):
    ai.refresh(snapshot,connect,candidate_loader=candidates)
