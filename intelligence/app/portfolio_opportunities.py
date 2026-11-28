"""Public-only bounded research projection for owner-local portfolio comparison."""
from datetime import date, datetime
from math import isfinite
import re
from zoneinfo import ZoneInfo

EQUITY_HORIZONS = ("LONG_TERM", "SHORT_TERM", "SWING")
FUND_CATEGORIES = ("LARGE_CAP", "MID_CAP", "SMALL_CAP", "FLEXI_CAP", "INDEX")

def _fresh(value, today, age, completed=False):
    try:
        observed = date.fromisoformat(value)
        return (1 if completed else 0) <= (today-observed).days <= age
    except (ValueError, TypeError):
        return False

def _number(value):
    return type(value) in (int, float) and isfinite(value)

def project(snapshot, today):
    output = {"status":"DISABLED" if not snapshot.get("enabled") else "NO_CURRENT_WATCH_EVIDENCE",
              "equities":[], "funds":[], "ready_sections":[], "blocked_sections":[],
              "notice":"Technical and historical watches only; no investment recommendation or suitability verdict."}
    if not snapshot.get("enabled"):
        return output
    seen_equity, seen_fund = set(), set()
    for section in snapshot.get("sections", []):
        name = section.get("section")
        if name not in ("NSE","BSE",*FUND_CATEGORIES):
            continue
        if section.get("status") != "READY":
            output["blocked_sections"].append(name)
            continue
        output["ready_sections"].append(name)
        result = section.get("result") or {}
        if name in ("NSE","BSE"):
            from .sector_price_context import _point
            coverage=result.get("discovery_coverage") or {}
            universe=result.get("company_research_universe") or []
            indexed={}
            if (isinstance(universe,list) and len(universe)<=20000 and coverage.get("calendar_status")=="PUBLISHED_SESSION"
                and coverage.get("calendar_checked_on")==today.isoformat()):
                for row in universe:
                    if not isinstance(row,dict):continue
                    identity=row.get("isin")
                    if not isinstance(identity,str):continue
                    indexed[identity]=row if identity not in indexed else None
            for horizon in EQUITY_HORIZONS:
                group = result.get("horizons", {}).get(horizon, {})
                if group.get("status") != "TECHNICAL_WATCH_ONLY":
                    continue
                for item in group.get("candidates", [])[:5]:
                    isin, symbol = item.get("isin"), item.get("symbol")
                    if (not isinstance(isin,str) or not re.fullmatch(r"IN[A-Z0-9]{10}",isin)
                        or not isinstance(symbol,str) or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",symbol)
                        or item.get("exchange") != name or not _fresh(item.get("as_of"),today,4,True)
                        or isin in seen_equity):
                        continue
                    company = item.get("company_evidence") or {}
                    profile = company.get("sections",{}).get("profile",{}).get("data") or {}
                    sector = profile.get("sector") if company.get("isin")==isin else None
                    matched=None
                    raw=indexed.get(isin)
                    if (raw and name=="NSE" and raw.get("exchange")==name and type(raw.get("id")) is int
                        and raw.get("id")==item.get("id") and raw.get("as_of")==item["as_of"]==coverage.get("expected_session")
                        and raw.get("security_state") not in ("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED")
                        and item.get("adjustment_status")=="ADJUSTED"):
                        point=_point((raw.get("comparative_price_windows") or {}).get("60"),item["as_of"])
                        if point and point[0][3]=="UPSTOX":
                            scope,value=point
                            matched={"first_date":scope[0],"last_date":scope[1],"dates_digest":scope[2],"return_percent":value}
                    seen_equity.add(isin)
                    output["equities"].append({"isin":isin,"symbol":symbol,"exchange":name,"horizon":horizon,
                        "as_of":item["as_of"],"sector":sector[:180] if isinstance(sector,str) else None,
                        "adjustment_status":item.get("adjustment_status"),
                        "blockers":group.get("blockers",[])[:10],"matched_60":matched,"evidence_type":"TECHNICAL_WATCH_ONLY"})
        else:
            history = result.get("historical_coverage") or {}
            if history.get("status") != "HISTORICAL_WATCH_ONLY":
                continue
            for item in history.get("items",[])[:5]:
                code, title = item.get("scheme_code"), item.get("scheme_name")
                if (type(code) is not int or not 0<code<10**18 or code in seen_fund or not isinstance(title,str)
                    or not title.strip() or item.get("nav_date")!=history.get("comparison_date")
                    or not _fresh(item.get("nav_date"),today,7)
                    or not _number(item.get("cagr_3y_percent")) or not _number(item.get("drawdown_3y_percent"))
                    or not -100<=item["drawdown_3y_percent"]<=0):
                    continue
                weekly=item.get("matched_weekly_comparison") or {}
                matched=None
                if (item.get("amfi_plan")=="DIRECT" and item.get("amfi_option")=="GROWTH"
                    and isinstance(item.get("isin_growth"),str) and re.fullmatch(r"INF[A-Z0-9]{9}",item["isin_growth"])
                    and weekly.get("methodology")=="MF-WEEKLY-MATCH-1" and weekly.get("anchor_count")==157
                    and weekly.get("last_date")==item["nav_date"] and isinstance(weekly.get("date_digest"),str)
                    and re.fullmatch(r"[a-f0-9]{64}",weekly["date_digest"])
                    and all(_number(weekly.get(k)) for k in ("cagr_percent","drawdown_percent"))
                    and -100<=weekly["drawdown_percent"]<=0):
                    matched={k:weekly.get(k) for k in ("first_date","last_date","date_digest","cagr_percent","drawdown_percent")}
                seen_fund.add(code)
                output["funds"].append({"scheme_code":str(code),"name":title[:300],"category":name,
                    "as_of":item["nav_date"],"cagr_3y_percent":item["cagr_3y_percent"],
                    "drawdown_3y_percent":item["drawdown_3y_percent"],"matched_weekly":matched,"isin_growth":item.get("isin_growth") if matched else None,
                    "evidence_type":"HISTORICAL_WATCH_ONLY"})
    if output["equities"] or output["funds"]:
        output["status"]="WATCH_EVIDENCE_AVAILABLE"
    return output

def read():
    from . import autonomous_research, automatic_company_evidence
    snapshot=autonomous_research.read_snapshot(include_ai=False)
    automatic_company_evidence.attach(snapshot,autonomous_research._connect)
    return project(snapshot, datetime.now(ZoneInfo("Asia/Kolkata")).date())
