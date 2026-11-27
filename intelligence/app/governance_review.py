"""Explicit governance review gaps; positive surveillance is not a misconduct verdict."""
from . import shareholding_research
REQUIRED=("OFFICIAL_ASM_GSM_ESM_AND_TRADE_RESTRICTIONS_REQUIRED","INDEPENDENT_PROMOTER_PLEDGE_AND_ENCUMBRANCE_REQUIRED","AUDITOR_AND_REGULATORY_EVENT_VERIFICATION_REQUIRED")
SPECIAL=("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED")
def assess(row,report,today):
    state=row.get("security_state","UNKNOWN")
    if state not in ("NORMAL","UNKNOWN",*SPECIAL):state="UNKNOWN"
    findings=[]
    if state in SPECIAL:findings.append("REPORTED_"+state+"_REVIEW")
    ownership=shareholding_research.summarize(report,today) if report.get("isin")==row.get("isin") and row.get("isin") else {}
    for item in ownership.get("review_prompts",[]):
        if item.get("category")=="promoters":findings.append("REPORTED_PROMOTER_OWNERSHIP_DECLINE_REVIEW")
    return {"status":"REVIEW_REQUIRED" if findings else "INCOMPLETE_GOVERNANCE_EVIDENCE",
            "provider_security_state":state,"ownership_status":ownership.get("status","UNAVAILABLE"),
            "ownership_period":ownership.get("latest_period"),"findings":findings,"blockers":list(REQUIRED),
            "clearance_verified":False,"notice":"Provider classification and reported ownership only. NORMAL is not exchange clearance; a restriction or ownership decline is not proof of wrongdoing. No pledge or auditor inference."}
