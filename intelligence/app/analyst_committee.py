"""Bounded multi-model decision review over the current public analyst report.

Models choose evidence-supported research priorities, not trades. No free model
prose is published; deterministic rules remain authoritative. Same provider
consent and budget as automatic AI review, no private input and no GET calls.
"""
from datetime import datetime,timedelta
from hashlib import sha256
import json
import re
from . import automatic_ai_review as ai, ai_failover
from .investment_analyst import obj, rows, num

VERSION="ANALYST-COMMITTEE-1"
NOTICE="Model judgments are conditional research priorities, not independently verified facts, return probabilities or order instructions. Disagreement is caution, not a vote to trade."
TIERS={"ADJUSTED_JOINT","REPORTED_JOINT","BUSINESS_SCREEN","TECHNICAL_LEAD","DRIVER_SUPPORTED","HISTORICAL_ONLY","DRIVER_REVIEW"}
REASONS={
 "JOINT_SCREEN":"Joint price and reported business screen supports further review.",
 "BUSINESS_SCREEN":"Reported business evidence supports investigation.",
 "GROWTH_AND_VALUATION":"Reported earnings growth and relative P/E support investigation; valuation date unverified.",
 "VALUATION_CAUTION":"Reported relative P/E is above the reported sector multiple; verify valuation.",
 "HISTORICAL_PEERS":"Historical peer comparison supports further investigation.",
 "GROWTH_DRIVERS":"Reported underlying growth drivers support further review.",
 "POSITIVE_SCENARIO":"Uncalibrated earnings scenario is positive; verify assumptions.",
 "NEGATIVE_SCENARIO":"Uncalibrated earnings scenario indicates potential weakness.",
 "HIGH_HISTORICAL_RISK":"Observed price or peer-relative downside warrants caution.",
 "ADJUSTMENT_UNKNOWN":"Price adjustment is not independently verified.",
 "DRIVER_RISK":"Reported underlying-business evidence requires review.",
 "LIMITED_EVIDENCE":"Missing independent evidence limits the conclusion.",
}
def pack(report):
    if report.get("status")!="RESEARCH_AVAILABLE":return {}
    out={}
    def add(key,row,group,identity):
        tier=row.get("tier")
        if tier not in TIERS or row.get("qualified") is not False:return
        score=row.get("score");g=obj(row.get("growth_outlook"))
        risk=row.get("risk") or row.get("relative_risk")
        risk=risk if risk in ("LOW","MEDIUM","HIGH","ABOVE_PEER_MEDIAN_DOWNSIDE","AT_OR_BELOW_PEER_MEDIAN_DOWNSIDE") else None
        scenario=[g.get("revenue_yoy_percent"),g.get("profit_yoy_percent")]
        if not all(num(v,-50,100) for v in scenario):scenario=None
        raw=obj(row.get("observed_facts"))
        bounds={"earnings_growth_percent":(10,100),"eps_growth_percent":(10,100),"sales_growth_percent":(5,10000),
            "reported_pe":(.0001,40),"reported_sector_pe":(.0001,1e6),"median_daily_turnover_cr":(5,1e10),
            "atr_percent":(.01,5),"return_60_percent":(-100,100),"historical_cagr_percent":(.00001,1e6),
            "joint_coverage_weight_percent":(70,100.5),"joint_growth_weight_percent":(0,100.5),"review_weight_percent":(0,100.5)}
        facts={k:round(raw[k],4) for k,(lo,hi) in bounds.items() if num(raw.get(k),lo,hi)}
        allowed=["LIMITED_EVIDENCE"]
        if tier in ("ADJUSTED_JOINT","REPORTED_JOINT","BUSINESS_SCREEN") and all(k in facts for k in ("earnings_growth_percent","reported_pe","reported_sector_pe")):
            if facts["reported_pe"]<=facts["reported_sector_pe"] and facts["earnings_growth_percent"]>=15:allowed.append("GROWTH_AND_VALUATION")
            elif facts["reported_pe"]>facts["reported_sector_pe"]:allowed.append("VALUATION_CAUTION")
        if tier=="ADJUSTED_JOINT":allowed.append("JOINT_SCREEN")
        if tier=="REPORTED_JOINT":allowed.extend(["JOINT_SCREEN","ADJUSTMENT_UNKNOWN"])
        if tier=="BUSINESS_SCREEN":allowed.append("BUSINESS_SCREEN")
        if tier in ("DRIVER_SUPPORTED","HISTORICAL_ONLY","DRIVER_REVIEW"):allowed.append("HISTORICAL_PEERS")
        if tier=="DRIVER_SUPPORTED":allowed.append("GROWTH_DRIVERS")
        if tier=="DRIVER_REVIEW":allowed.append("DRIVER_RISK")
        if risk in ("HIGH","ABOVE_PEER_MEDIAN_DOWNSIDE"):allowed.append("HIGH_HISTORICAL_RISK")
        if scenario and min(scenario)>0:allowed.append("POSITIVE_SCENARIO")
        if scenario and min(scenario)<0:allowed.append("NEGATIVE_SCENARIO")
        out[key]={"identity":identity,"group":group,"tier":tier,"date":row.get("as_of",row.get("nav_date")),
            "score":score if num(score,0,100) else None,"risk":risk,"earnings_scenario":scenario,"facts":facts,
            "allowed_reasons":allowed}
    for i,r in enumerate(rows(report.get("stocks"))[:6]):
        if isinstance(r,dict) and re.fullmatch(r"INE[A-Z0-9]{9}",str(r.get("isin",""))):add("S"+str(i+1),r,"EQUITY",r["isin"])
    for group in rows(report.get("funds"))[:3]:
        category=group.get("category")
        if category not in ("LARGE_CAP","MID_CAP","SMALL_CAP"):continue
        for i,r in enumerate(rows(group.get("items"))[:3]):
            if isinstance(r,dict) and re.fullmatch(r"[1-9][0-9]{5,8}",str(r.get("identifier",""))):add(category+str(i+1),r,category,r["identifier"])
    return out

def key(evidence,providers,today):
    return sha256(json.dumps([VERSION,today,evidence,providers],sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def validate(response,evidence):
    """Retain only allowed decision/rationale pairs with exact candidate citations."""
    found={};duplicate=set()
    for r in rows(obj(response).get("findings"))[:8]:
        try:
            if not isinstance(r,dict) or not isinstance(r.get("statement"),str) or len(r["statement"])>500:continue
            v=json.loads(r["statement"])
            if set(v)!={"candidate","decision","reason"}:continue
            candidate=v["candidate"];decision=v["decision"];reason=v["reason"]
            if candidate not in evidence or r.get("evidence_ids")!=[candidate] or reason not in evidence[candidate]["allowed_reasons"]:continue
            if decision not in ("PRIORITIZE_REVIEW","DEFER_REVIEW"):continue
            if decision=="PRIORITIZE_REVIEW" and (reason not in ("JOINT_SCREEN","BUSINESS_SCREEN","HISTORICAL_PEERS","GROWTH_DRIVERS","POSITIVE_SCENARIO","GROWTH_AND_VALUATION")
                or evidence[candidate]["tier"]=="DRIVER_REVIEW"):continue
            if decision=="DEFER_REVIEW" and reason not in ("LIMITED_EVIDENCE","HIGH_HISTORICAL_RISK","ADJUSTMENT_UNKNOWN","DRIVER_RISK","NEGATIVE_SCENARIO","VALUATION_CAUTION"):continue
            if candidate in found:duplicate.add(candidate)
            found[candidate]={"decision":decision,"reason":reason}
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return {k:v for k,v in found.items() if k not in duplicate}

def refresh(report,connect,instant,runner=ai_failover.grounded_research):
    providers=ai.providers();evidence=pack(report)
    if not providers or not evidence:return False
    digest=key(evidence,providers,report["research_date"])
    previous=ai._claim(connect,digest,instant)
    if previous is None:return False
    reviews=obj(previous.get("decisions"));attempted=set(rows(previous.get("attempted")))&set(providers)
    pending=[p for p in providers if p not in attempted]
    if not pending:
        attempted=set(reviews);pending=[p for p in providers if p not in attempted]
    if not pending:
        ai._finish(connect,digest,instant,"COMPLETE",{"decisions":reviews,"attempted":sorted(attempted)})
        return bool(reviews)
    p=pending[0];attempted.add(p)
    try:
        prompt=("Act as an investment research committee member. Compare candidates only within their group and evidence tier. "
            "Select the strongest research priority or caution; do not give buy/sell, allocations or forecasts. "
            "Return up to eight findings, each statement a JSON string with exactly candidate, decision, reason. "
            "decision must be PRIORITIZE_REVIEW or DEFER_REVIEW. Use only allowed_reasons for that candidate; "
            "cite exactly its candidate ID. No prose is retained. A score is not return probability. "
            "A positive earnings scenario is an uncalibrated assumption, not a forecast. Evidence: "+
            json.dumps(evidence,separators=(",",":"),ensure_ascii=True,allow_nan=False))
        result=runner(prompt,list(evidence),providers=[p])
        if result.get("status")=="MODEL_GROUNDED" and result.get("provider")==p:
            valid=validate(result.get("response"),evidence)
            if valid:reviews[p]=valid
    except Exception:pass
    status="COMPLETE" if set(reviews)==set(providers) else "PENDING_MEMBERS" if set(providers)-attempted else "PARTIAL" if reviews else "UNAVAILABLE"
    ai._finish(connect,digest,instant,status,{"decisions":reviews,"attempted":sorted(attempted)})
    return bool(reviews)

def attach(report,connect,instant):
    providers=ai.providers();evidence=pack(report)
    result={"methodology":VERSION,"status":"AWAITING_REVIEW" if providers and evidence else "DISABLED_OR_NO_EVIDENCE",
        "reviewed_providers":0,"notice":NOTICE}
    report["committee"]=result
    if not providers or not evidence:return report
    cached=ai._read(connect,key(evidence,providers,report["research_date"]))
    if not cached or cached[1] not in ("COMPLETE","PENDING_MEMBERS","PARTIAL","RUNNING"):return report
    try:
        stamp=datetime.fromisoformat(cached[0])
        if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant:return report
    except (TypeError,ValueError):return report
    decisions=obj(obj(cached[2]).get("decisions"))
    accepted={}
    for p in providers:
        raw=obj(decisions.get(p))
        v=validate({"findings":[{"statement":json.dumps({"candidate":k,**d}),"evidence_ids":[k]} for k,d in raw.items() if isinstance(d,dict)]},evidence)
        if v:accepted[p]=v
    result.update(status="REVIEW_AVAILABLE" if accepted else "AWAITING_REVIEW",reviewed_providers=len(accepted))
    def annotate(row,k):
        votes=[(p,v[k]) for p,v in accepted.items() if k in v]
        if not votes:return
        decisions={v["decision"] for _,v in votes}
        state="DISAGREEMENT" if len(decisions)>1 else next(iter(decisions))
        row["ai_review"]={"state":state,"providers":[p for p,_ in votes],"reasons":[REASONS[c] for c in sorted({v["reason"] for _,v in votes})]}
        if state in ("DISAGREEMENT","DEFER_REVIEW"):row["action"]="WATCH_FOR_CONFIRMATION" if row.get("action")!="REVIEW_BEFORE_NEW_SIP" else row["action"]
    for i,r in enumerate(report["stocks"]):annotate(r,"S"+str(i+1))
    for g in report["funds"]:
        for i,r in enumerate(g["items"]):annotate(r,g["category"]+str(i+1))
    return report
