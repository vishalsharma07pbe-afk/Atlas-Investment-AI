"""Explicit governance review gaps; positive surveillance is not a misconduct verdict."""
from . import shareholding_research
REQUIRED=("OFFICIAL_ASM_GSM_ESM_AND_TRADE_RESTRICTIONS_REQUIRED","INDEPENDENT_PROMOTER_PLEDGE_AND_ENCUMBRANCE_REQUIRED","AUDITOR_AND_REGULATORY_EVENT_VERIFICATION_REQUIRED")
SPECIAL=("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED")
def assess(row,report,today):
    state=row.get("security_state","UNKNOWN")
    if state not in ("NORMAL","UNKNOWN",*SPECIAL):state="UNKNOWN"
    surveillance=row.get("exchange_surveillance") or {}
    findings=list(surveillance.get("findings",[])) if surveillance.get("source_exchange")==row.get("exchange") else []
    if state in SPECIAL:findings.append("REPORTED_"+state+"_REVIEW")
    ownership=shareholding_research.summarize(report,today) if report.get("isin")==row.get("isin") and row.get("isin") else {}
    for item in ownership.get("review_prompts",[]):
        if item.get("category")=="promoters":findings.append("REPORTED_PROMOTER_OWNERSHIP_DECLINE_REVIEW")
    pledge=row.get("independent_pledge_evidence") or {}
    if pledge.get("isin")==row.get("isin") and pledge.get("status")=="REPORTED_QUARTERLY_AGGREGATE":
        if pledge.get("total_encumbered_shares",0)>0:findings.append("ISSUER_REPORTED_PROMOTER_ENCUMBRANCE_REVIEW")
        if pledge.get("pledged_shares",0)>0:findings.append("ISSUER_REPORTED_PROMOTER_PLEDGE_REVIEW")
    else:pledge={}
    return {"status":"REVIEW_REQUIRED" if findings else "INCOMPLETE_GOVERNANCE_EVIDENCE",
            "provider_security_state":state,"ownership_status":ownership.get("status","UNAVAILABLE"),
            "ownership_period":ownership.get("latest_period"),"findings":sorted(set(findings)),"exchange_surveillance":surveillance or None,"independent_pledge_evidence":pledge or None,"blockers":list(REQUIRED),
            "clearance_verified":False,"notice":"Provider classification, reported ownership and available independent exchange cautions only. NORMAL is not exchange clearance; a restriction or ownership decline is not proof of wrongdoing. Cautions do not verify pledge percentages or auditor conclusions."}
