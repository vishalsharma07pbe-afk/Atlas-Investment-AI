"""Deterministic cross-venue watch selection; never a qualification producer.

Only exact public ISIN groups are consolidated. No price, replay, company or
execution evidence is copied between venues. Keep the original per-listing
assessment and a conservative union of its requirements and findings.
"""
from collections import defaultdict
from math import isfinite
from .replay_evidence import exact_isin
from . import company_venues

NOTICE=("Distinct ISINs in already shortlisted current venue samples, not a full-market scan. "
        "Representative uses current technical observation checks, comparable observed venue preference when available, then technical score and historical turnover; "
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

def summarize(observations,ready_markets,venue_observations=None,instant=None):
    listings=defaultdict(list)
    for item,decision in observations:
        item.pop("selection_company_context",None)
        item.pop("company_venue_context",None)
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
        eligible=[i for i,d in entries if _technical(i,d) and i.get("security_state") not in company_venues.SPECIAL]
        def rank(i):
            return (-_score(i.get("rank_score")),-_score(i.get("median_daily_traded_value")),i["exchange"],i["symbol"],i["id"])
        chosen=min(eligible,key=rank) if eligible and isin not in conflicting_isins else None
        venue_context=None
        if venue_observations is not None and instant is not None:
            rows=venue_observations.get(isin,[])
            # Preserve known restrictions even when a listing is outside this
            # horizon's small technical shortlist. Never substitute its data.
            findings.update("REPORTED_"+r["security_state"]+"_AT_"+r["exchange"]
                            for r in rows if r.get("security_state") in company_venues.SPECIAL)
            findings.update(f for r in rows for f in (r.get("exchange_surveillance") or {}).get("findings",[]))
            if chosen is not None:
                consolidated=company_venues.consolidate(eligible,venue_observations,instant,rank)
                if consolidated:
                    selected=consolidated[0]
                    venue_context=selected["company_venue_context"]
                    chosen=next(i for i in eligible if _key(i)==_key(selected))
                    findings.update(venue_context["review_findings"])
                else:
                    chosen=None
                    findings.add("CONFLICTING_OR_RESTRICTED_VENUE_OBSERVATIONS")
                    blockers.add("CONFLICTING_OR_RESTRICTED_VENUE_OBSERVATIONS")
        if findings:
            review_companies+=1
        context={"listing_count":len(entries),"venues":venues,"blockers":sorted(blockers),
                 "review_findings":sorted(findings),"status":"COMPANY_REVIEW_REQUIRED" if findings else "COMPANY_UNQUALIFIED"}
        for item,_ in entries:
            item["selection_company_context"]=context
            if venue_context is not None:
                item["company_venue_context"]=venue_context
        if chosen is not None:
            representatives.append(chosen)
    representatives.sort(key=lambda i:(-_score(i.get("rank_score")),-_score(i.get("median_daily_traded_value")),i["isin"],i["exchange"],i["id"]))
    return {"unique_company_count":len(groups),"unidentified_listing_count":unidentified,
            "conflicting_listing_count":conflicts,"cross_venue_company_count":both,
            "review_company_count":review_companies,"ready_markets":sorted(ready_markets),
            "watch_refs":[{"exchange":i["exchange"],"id":i["id"],"isin":i["isin"]} for i in representatives[:5]],
            "notice":NOTICE}
