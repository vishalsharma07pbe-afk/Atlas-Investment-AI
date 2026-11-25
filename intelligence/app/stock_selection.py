"""Deterministic cross-venue watch selection; never a qualification producer.

Only exact public ISIN groups are consolidated. No price, replay, company or
execution evidence is copied between venues. Keep the original per-listing
assessment and a conservative union of its requirements and findings.
"""
from collections import defaultdict
from math import isfinite
from .replay_evidence import exact_isin

NOTICE=("Distinct ISINs in already shortlisted current venue samples, not a full-market scan. "
        "Representative uses current technical observation checks, then technical score and historical turnover; "
        "not expected return, verified execution liquidity or investment rank. "
        "Unidentified or conflicting registry listings do not enter the consolidated watch shortlist. "
        "All company-level blockers and findings from reviewed listings remain visible.")

def _numeric(value):
    return type(value) in (float,int) and isfinite(value)

def _score(value):
    return value if _numeric(value) else float("-inf")

def _key(item):
    return item["exchange"],item["id"]

def _signature(item,decision):
    # Any conflicting duplicate of a venue registry ID is withheld. Even
    # identical identity/price records with differing assessments cannot merge.
    return (item.get("isin"),item.get("symbol"),item.get("as_of"),item.get("close"),
            item.get("rank_score"),item.get("median_daily_traded_value"),item.get("adjustment_status"),
            decision.get("status"),tuple(decision.get("blockers",[])),tuple(decision.get("review_findings",[])),
            tuple((g.get("domain"),g.get("status"),tuple(g.get("requirements",[]))) for g in decision.get("gates",[])))

def _technical(item,decision):
    return (item.get("adjustment_status")=="ADJUSTED"
            and _numeric(item.get("rank_score"))
            and _numeric(item.get("close")) and item["close"]>0
            and any(g.get("domain")=="TECHNICAL" and g.get("status")=="OBSERVATION_CHECKS_MET"
                    for g in decision.get("gates",[])))

def summarize(observations,ready_markets):
    listings=defaultdict(list)
    for item,decision in observations:
        item.pop("selection_company_context",None)
        listings[_key(item)].append((item,decision))
    groups=defaultdict(list)
    unidentified=0
    conflicts=0
    conflicting_isins=set()
    for entries in listings.values():
        first=entries[0]
        if any(_signature(*entry)!=_signature(*first) for entry in entries[1:]):
            conflicts+=1
            conflicting_isins.update(item["isin"] for item,_ in entries if exact_isin(item.get("isin")))
            continue
        item,decision=first
        if not exact_isin(item.get("isin")):
            unidentified+=1
            continue
        groups[item["isin"]].append((item,decision))
    representatives=[]
    review_companies=0
    both=0
    for isin,entries in sorted(groups.items()):
        venues=sorted({i["exchange"] for i,_ in entries})
        if len(venues)>1:
            both+=1
        blockers={code for _,d in entries for code in d.get("blockers",[])}
        findings={code for _,d in entries for code in d.get("review_findings",[])}
        if isin in conflicting_isins:
            blockers.add("CONFLICTING_VENUE_LISTING_EVIDENCE")
            findings.add("CONFLICTING_VENUE_LISTING_EVIDENCE")
        if findings:
            review_companies+=1
        context={"listing_count":len(entries),"venues":venues,"blockers":sorted(blockers),
                 "review_findings":sorted(findings),"status":"COMPANY_REVIEW_REQUIRED" if findings else "COMPANY_UNQUALIFIED"}
        for item,_ in entries:
            item["selection_company_context"]=context
        eligible=[i for i,d in entries if _technical(i,d)]
        if not eligible or isin in conflicting_isins:
            continue
        # No ranking by model count, missing gate count or private holdings.
        eligible.sort(key=lambda i:(-_score(i.get("rank_score")),-_score(i.get("median_daily_traded_value")),i["exchange"],i["symbol"],i["id"]))
        representatives.append(eligible[0])
    representatives.sort(key=lambda i:(-_score(i.get("rank_score")),-_score(i.get("median_daily_traded_value")),i["isin"],i["exchange"],i["id"]))
    return {"unique_company_count":len(groups),"unidentified_listing_count":unidentified,
            "conflicting_listing_count":conflicts,"cross_venue_company_count":both,
            "review_company_count":review_companies,"ready_markets":sorted(ready_markets),
            "watch_refs":[{"exchange":i["exchange"],"id":i["id"],"isin":i["isin"]} for i in representatives[:5]],
            "notice":NOTICE}
