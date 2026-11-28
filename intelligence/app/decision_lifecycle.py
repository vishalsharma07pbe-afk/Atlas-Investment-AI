"""Local public research lifecycle and recoverable evidence routing.

Read immutable stock/fund watch publications; absence from today's bounded
shortlist is not deterioration or an exit. Never inspect private holdings.
"""
from contextlib import closing
from datetime import timedelta
import json
from . import decision_quality as q, watch_outcomes as w, decision_outcomes as outcomes
from .replay_evidence import exact_isin

VERSION="PUBLIC-DECISION-LIFECYCLE-1"
NOTICE="Current research state versus original publication. Missing shortlist coverage is not a sell signal. Existing source permissions, due gates and cooldowns govern recovery."
ROUTES={
 "CURRENT_COMPLETED_SESSION":"SECTION:MARKET","ADJUSTED_JOINT_SCREEN":"SECTION:MARKET",
 "REPORTED_EARNINGS_AND_EPS_GROWTH":"COMPANY_EVIDENCE","REPORTED_RELATIVE_VALUATION":"COMPANY_EVIDENCE",
 "OBSERVED_LIQUIDITY":"SECTION:MARKET","VALID_PRICE_RISK_SCENARIO":"SECTION:MARKET",
 "CURRENT_QUARTER_SCENARIO":"COMPANY_EVIDENCE","SOURCE_BOUND_VALUE_SCENARIO":"OPERATOR_REVIEW_REQUIRED",
 "CURRENT_NAV":"SECTION:FUND","MATCHED_PEER_HISTORY":"SECTION:FUND","OBSERVED_DOWNSIDE_AND_VOLATILITY":"SECTION:FUND",
 "SUPPORTED_UNDERLYING_DRIVERS":"FUND_COMPANY_EVIDENCE","CURRENT_UNDERLYING_SCENARIO":"FUND_COMPANY_EVIDENCE",
 "MATCHED_DATED_TER":"OFFICIAL_AMFI_TER","MATCHED_TRI_HISTORY":"OFFICIAL_TRI_DOWNLOAD",
 "INDEPENDENT_FILING_CONFLICT":"NSE_FINANCIAL_FILINGS","CONFLICTING_FUND_EXPENSE_EVIDENCE":"OFFICIAL_AMFI_TER",
}
STATES=("PRIORITY_RESEARCH","EVIDENCE_INCOMPLETE","REVIEW_REQUIRED")

def original_stocks(connect,instant):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='watch_outcomes'").fetchone():return {}
        rows=db.execute("SELECT published_at,evidence,status FROM watch_outcomes WHERE horizon=? AND published_at BETWEEN ? AND ? ORDER BY published_at DESC,instrument_id LIMIT 500",(outcomes.HORIZON,(instant-timedelta(days=90)).isoformat(),instant.isoformat())).fetchall()
    result={}
    for row in rows:
        try:
            e=json.loads(row["evidence"]);isin=e.get("isin");state=e.get("decision_state")
            if e.get("methodology")!=outcomes.VERSION or e.get("decision_policy")!=q.VERSION or not exact_isin(isin) or state not in STATES:continue
            result.setdefault(isin,{"state":state,"published_at":row["published_at"],"outcome_status":row["status"]})
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return result

def attach(report,previous,job_status):
    tasks={};changes={}
    if report.get("status")!="RESEARCH_AVAILABLE":return {"methodology":VERSION,"status":"AWAITING_CURRENT_RESEARCH","recovery":[],"changes":{},"notice":NOTICE}
    def add(row,kind,category=None):
        quality=q.obj(row.get("decision_quality"));state=quality.get("state")
        if quality.get("methodology")!=q.VERSION or state not in STATES:return
        identity=row.get("isin") if kind=="STOCK" else row.get("identifier")
        if not isinstance(identity,str):return
        if kind=="STOCK":
            original=previous.get(identity)
            if original:
                old=original["state"]
                status="ADVERSE_CHANGE_REVIEW" if old!="REVIEW_REQUIRED" and state=="REVIEW_REQUIRED" else "EVIDENCE_LOST_REVIEW" if old=="PRIORITY_RESEARCH" and state=="EVIDENCE_INCOMPLETE" else "RESEARCH_STATE_CHANGED" if old!=state else "UNCHANGED"
                row["lifecycle"]={"status":status,"original_state":old,"current_state":state,"published_at":original["published_at"],"outcome_status":original["outcome_status"]}
                changes[status]=changes.get(status,0)+1
        for code in set(q.rows(quality.get("missing_checks"))+q.rows(quality.get("adverse_findings"))):
            if not isinstance(code,str) or code not in ROUTES:continue
            route=ROUTES[code]
            if route=="SECTION:MARKET":
                if row.get("exchange") not in ("NSE","BSE"):continue
                route="SECTION:"+row["exchange"]
            if route=="SECTION:FUND":
                if category not in ("LARGE_CAP","MID_CAP","SMALL_CAP"):continue
                route="SECTION:"+category
            entry=tasks.setdefault(route,{"job":route,"identities":set(),"missing_codes":set()})
            entry["identities"].add((kind,identity));entry["missing_codes"].add(code)
    for r in q.rows(report.get("stocks")):add(r,"STOCK")
    for group in q.rows(report.get("funds")):
        for r in q.rows(group.get("items")):add(r,"FUND",group.get("category"))
    indexed={j["job"]:j for j in q.rows(job_status.get("jobs")) if isinstance(j,dict) and isinstance(j.get("job"),str)}
    recovery=[]
    for job,t in sorted(tasks.items(),key=lambda kv:(-len(kv[1]["identities"]),kv[0])):
        j=indexed.get(job,{})
        recovery.append({"job":job,"affected_candidates":len(t["identities"]),"missing_codes":sorted(t["missing_codes"]),
            "status":"MANUAL_EVIDENCE_REQUIRED" if job=="OPERATOR_REVIEW_REQUIRED" else j.get("status","PENDING"),"next_due_at":j.get("next_due_at")})
    return {"methodology":VERSION,"status":"CURRENT_REVIEW","recovery":recovery,"changes":changes,"notice":NOTICE}
