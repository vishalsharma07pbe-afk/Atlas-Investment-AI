"""One evidence-first decision desk over current saved public research.

No new provider calls, private holdings, model prompts, target generation, or
qualification rules. Preserve separate strategies and never rank across assets.
"""
from collections import Counter
from datetime import date
import re
from .replay_evidence import exact_isin
from .fund_categories import CATEGORIES
from . import company_reports, stock_qualification, elite_assessment

VERSION="UNIFIED-DECISION-1"
NOTICE=("Research priority only, not investment advice, suitability, confidence or execution clearance. "
        "AI assertions match supplied observations, not independent truth. Mandatory qualification gates "
        "remain authoritative. Intraday session and private portfolio reviews are separate workflows.")
HORIZONS=("SWING","SHORT_TERM","LONG_TERM","ELITE")

def codes(values):
    return sorted({v for v in values if isinstance(v,str) and re.fullmatch(r"[A-Z0-9_]{1,180}",v)}) if isinstance(values,list) else []

def _fresh(day,today,age=4,minimum=1):
    try:return minimum<=(today-date.fromisoformat(day)).days<=age
    except (ValueError,TypeError):return False

def _ai(item,isin):
    report=item.get("ai_review") or {}
    if report.get("company_isin")!=isin:return {"status":"UNAVAILABLE","reviewed_count":None}
    committee=report.get("committee") or {}
    audit=committee.get("claim_comparison") or {}
    count=committee.get("reviewed_count")
    status=audit.get("status")
    if type(count) is not int or not 1<=count<=5 or status not in (
        "CONFLICTING_ASSERTIONS","CONTRADICTED_ASSERTIONS_PRESENT","SHARED_MATCHED_OBSERVATIONS_ONLY",
        "NO_SHARED_COMPARABLE_ASSERTIONS","NOT_ASSESSED"):
        return {"status":"UNAVAILABLE","reviewed_count":None}
    return {"status":status,"reviewed_count":count}

def _stock(item,horizon):
    gate=item.get("elite_assessment" if horizon=="ELITE" else "stock_qualification") or {}
    version=elite_assessment.VERSION if horizon=="ELITE" else stock_qualification.VERSION
    if gate.get("methodology")!=version:return None
    if horizon=="ELITE":
        if gate.get("status") not in ("PRELIMINARY_SCORE_ONLY","SCORE_WITHHELD") or gate.get("qualified") is not False:return None
    elif gate.get("horizon")!=horizon or gate.get("status") not in ("WITHHELD_EVIDENCE_GAPS","WITHHELD_REVIEW_REQUIRED"):return None
    blockers=codes(gate.get("blockers"))
    if "FINAL_QUALIFICATION_VALIDATION_REQUIRED" not in blockers:return None
    findings=set(codes(gate.get("review_findings")))
    for block in ("governance_review","selection_company_context","company_venue_context"):
        detail=item.get(block) or {}
        findings.update(codes(detail.get("review_findings")))
        if block=="governance_review":findings.update(codes(detail.get("findings")))
    ai=_ai(item,item["isin"])
    if ai["status"] in ("CONFLICTING_ASSERTIONS","CONTRADICTED_ASSERTIONS_PRESENT"):
        findings.add("AI_ASSERTIONS_CONTRADICT_SUPPLIED_EVIDENCE")
    attention=bool(findings) or gate.get("status")=="WITHHELD_REVIEW_REQUIRED"
    return {"isin":item["isin"],"id":item["id"],"exchange":item["exchange"],"symbol":item.get("symbol"),
            "as_of":item["as_of"],"horizon":horizon,"state":"REVIEW_REQUIRED" if attention else "WATCH_ONLY",
            "qualified":False,"blockers":blockers,"review_findings":sorted(findings),"ai":ai}

def summarize(snapshot,today):
    out={"methodology":VERSION,"status":"DISABLED","equity_companies":[],"fund_categories":[],
         "equity_company_count":None,"equity_review_count":None,"ai_reviewed_company_count":None,
         "intraday":{"status":"SEPARATE_SESSION_WORKFLOW"},"portfolio":{"status":"SEPARATE_OWNER_LOCAL_WORKFLOW"},
         "notice":NOTICE}
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return out
    out["status"]="AWAITING_EVIDENCE"
    if snapshot.get("research_date")!=today.isoformat():return out
    # Respect canonical selections; do not resurrect rejected watches.
    selections=(snapshot.get("stock_qualification") or {}).get("horizons") or {}
    selected=set()
    for horizon in HORIZONS[:-1]:
        for ref in ((selections.get(horizon) or {}).get("selection") or {}).get("watch_refs",[])[:5]:
            if isinstance(ref,dict) and exact_isin(ref.get("isin")) and ref.get("exchange") in ("NSE","BSE") and type(ref.get("id")) is int:
                selected.add((horizon,ref["exchange"],ref["id"],ref["isin"]))
    # company_reports entries already validate venue/date/calendar and bounded shortlist.
    observations={}
    conflicting=set()
    for horizon,item in company_reports.entries(snapshot):
        if horizon!="ELITE" and (horizon,item["exchange"],item["id"],item["isin"]) not in selected:continue
        if not isinstance(item.get("symbol"),str) or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",item["symbol"]):continue
        decision=_stock(item,horizon)
        if decision is None:continue
        key=(item["isin"],horizon,item["exchange"],item["id"],item["as_of"])
        if key in observations and observations[key]!=decision:conflicting.add(key)
        observations[key]=decision
    companies={}
    for key,row in sorted(observations.items()):
        if key in conflicting:continue
        company=companies.setdefault(row["isin"],{"isin":row["isin"],"symbol":row["symbol"],"observations":[]})
        company["observations"].append(row)
    for company in companies.values():
        rows=company["observations"]
        company["state"]="REVIEW_REQUIRED" if any(r["state"]=="REVIEW_REQUIRED" for r in rows) else "WATCH_ONLY"
        company["qualified"]=False
        company["ai_reviewed"]=any(r["ai"]["reviewed_count"] is not None for r in rows)
    out["equity_companies"]=sorted(companies.values(),key=lambda c:(c["state"]!="REVIEW_REQUIRED",c["isin"]))
    projected={(r["horizon"],r["exchange"],r["id"],r["isin"]) for c in companies.values() for r in c["observations"] if r["horizon"]!="ELITE"}
    missing=selected-projected
    out["canonical_projection_complete"]=not missing
    out["missing_canonical_watch_count"]=len(missing)
    all_daily_processed=all((selections.get(h) or {}).get("qualified_count")==0 for h in HORIZONS[:-1])
    # A failed projection is neither a genuine zero nor complete coverage.
    out["equity_company_count"]=len(companies) if not missing and (companies or all_daily_processed) else None
    out["equity_review_count"]=sum(c["state"]=="REVIEW_REQUIRED" for c in companies.values()) if out["equity_company_count"] is not None else None
    out["ai_reviewed_company_count"]=sum(c["ai_reviewed"] for c in companies.values()) if out["equity_company_count"] is not None else None
    # Fund historical watches and existing qualification results remain distinct.
    # No per-scheme decision from unlinked historical shortlist evidence.
    for category in CATEGORIES:
        sections=[s for s in snapshot.get("sections",[]) if s.get("section")==category and s.get("status")=="READY"]
        if len(sections)!=1:continue
        result=sections[0].get("result") or {}
        if result.get("category")!=category:continue
        counts=result.get("qualification_counts") or {}
        evaluated,top,growth=(counts.get(k) for k in ("evaluated_count","top_eligible_count","growth_eligible_count"))
        valid=all(type(x) is int and 0<=x<=40 for x in (evaluated,top,growth)) and max(top,growth)<=evaluated
        blockers=Counter()
        if valid:
            for key in ("top_missing_gate_counts","growth_missing_gate_counts"):
                for k,v in (counts.get(key) or {}).items():
                    if codes([k]) and type(v) is int and 0<v<=evaluated:blockers[k]+=v
        watches=[]
        shortlist=result.get("historical_research_shortlist") or {}
        if shortlist.get("methodology")=="MF-MATCHED-PEER-1" and shortlist.get("status")=="HISTORICAL_SHORTLIST_AVAILABLE" and shortlist.get("category")==category:
            seen=set()
            for row in shortlist.get("items",[])[:5]:
                code=row.get("identifier")
                if not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{5,8}",code) or code in seen or row.get("nav_date")!=shortlist.get("last_date") or not _fresh(row.get("nav_date"),today,7,0) or row.get("qualified") is not False or row.get("status")!="HISTORICAL_RESEARCH_ONLY":continue
                seen.add(code)
                watches.append({"identifier":code,"name":row.get("name"),"nav_date":row["nav_date"],"state":"HISTORICAL_WATCH_ONLY","qualified":False})
        driver_review=result.get("growth_driver_review") or {}
        drivers=[{"identifier":row.get("identifier"),"state":row.get("state"),
                  "ai_status":((row.get("ai_review") or {}).get("committee") or {}).get("agreement_status","UNAVAILABLE")}
                 for row in driver_review.get("items",[])[:5] if row.get("qualified") is False]
        out["fund_categories"].append({"category":category,"state":"HISTORICAL_WATCH_ONLY" if watches else "EVIDENCE_REVIEW",
          "reviewed_count":evaluated if valid else None,"historical_watches":watches,
          "top_withheld_count":evaluated-top if valid else None,"growth_withheld_count":evaluated-growth if valid else None,
          "leading_blockers":[{"code":k,"count":v} for k,v in sorted(blockers.items(),key=lambda x:(-x[1],x[0]))][:5],
          "driver_reviews":drivers,
          "prospective_status":(result.get("prospective_validation") or {}).get("status","UNAVAILABLE"),
          "qualification_status":result.get("recommendation_status","UNAVAILABLE")})
    if companies or out["fund_categories"]:out["status"]="RESEARCH_CONTEXT_AVAILABLE"
    if missing:out["status"]="INCOMPLETE_DECISION_PROJECTION"
    return out
