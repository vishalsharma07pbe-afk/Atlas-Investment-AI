"""Result-first summary of the existing public research snapshot.

No provider requests, holdings, AI calls or new qualification rules. A technical
watch is not a qualified investment opportunity; unknown is not zero.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation

MARKETS=("NSE","BSE")
FUNDS=("LARGE_CAP","MID_CAP","SMALL_CAP","FLEXI_CAP","INDEX")
HORIZONS=("SWING","SHORT_TERM","LONG_TERM")


def _count(value):
    return value if type(value) is int and value>=0 else 0


def _direction(value):
    try:
        amount=Decimal(str(value))
        if not amount.is_finite():
            return "UNAVAILABLE"
        return "NET_BUYING" if amount>0 else "NET_SELLING" if amount<0 else "NET_FLAT"
    except (InvalidOperation,ValueError,TypeError):
        return "UNAVAILABLE"


def summarize(snapshot):
    enabled=snapshot.get("enabled") is True
    rows={s["section"]:s for s in snapshot.get("sections",[]) if s.get("section") in MARKETS+FUNDS}
    ready={k:s["result"] for k,s in rows.items() if enabled and s.get("status")=="READY"
           and isinstance(s.get("result"),dict)}
    pending=[k for k in MARKETS+FUNDS if k not in ready]
    blockers=Counter()
    horizons={}
    for horizon in HORIZONS:
        watches={}
        groups=0
        for market in MARKETS:
            group=ready.get(market,{}).get("horizons",{}).get(horizon,{})
            if not isinstance(group,dict) or "candidates" not in group:
                continue
            groups+=1
            if group.get("status")!="TECHNICAL_WATCH_ONLY":
                continue
            for candidate in group["candidates"]:
                if not isinstance(candidate,dict) or candidate.get("exchange")!=market or type(candidate.get("id")) is not int:
                    continue
                # Count exchange-specific displayed observations, not unique companies.
                watches[(market,candidate["id"])]=candidate
        review_count=0
        conflict_count=0
        for candidate in watches.values():
            reliability=candidate.get("research_reliability") or {}
            if reliability.get("status")=="REVIEW_CONFLICTING_EVIDENCE":
                conflict_count+=1
            if (candidate.get("ai_review") or {}).get("reviews"):
                review_count+=1
            for code in set(reliability.get("blockers",[])):
                if isinstance(code,str):
                    blockers[code]+=1
        horizons[horizon]={"status":"WATCH_ONLY" if watches else "NO_WATCHES" if groups else "PENDING",
            "displayed_watch_count":len(watches),"ai_reviewed_count":review_count,
            "conflicting_evidence_count":conflict_count,
            "qualified_count":None,"qualification_status":"FULL_QUALIFICATION_NOT_AVAILABLE"}
    fund_picks=set()
    historical=0
    for category in FUNDS:
        result=ready.get(category)
        if result is None:
            continue
        for pick in result.get("growth_outlook",[]):
            identifier=(pick.get("fund") or {}).get("identifier")
            if isinstance(identifier,str) and identifier:
                fund_picks.add(identifier)
        history=result.get("historical_coverage") or {}
        if history.get("status")=="HISTORICAL_WATCH_ONLY":
            historical+=len(history.get("items",[]))
    institutional=snapshot.get("institutional_activity") or {}
    pair=institutional.get("paired_five_date_window") if enabled and institutional.get("status")=="RECENT_PROVIDER_EVIDENCE" else None
    flow={"status":"UNAVAILABLE"}
    if isinstance(pair,dict) and isinstance(pair.get("dates"),list) and len(set(pair["dates"]))==5:
        fii,dii=_direction(pair.get("fii_net")),_direction(pair.get("dii_net"))
        if "UNAVAILABLE" not in (fii,dii):
            flow={"status":"RECENT_PAIRED_OBSERVATIONS","latest_date":max(pair["dates"]),
                  "fii_direction":fii,"dii_direction":dii,"observation_count":5}
    status="DISABLED" if not enabled else "PENDING" if not ready else "PARTIAL" if pending else "CURRENT_SECTIONS"
    return {"status":status,"ready_sections":len(ready),"total_sections":len(MARKETS+FUNDS),
        "pending_sections":pending,
        "market":{"eligible_histories":sum(_count(ready.get(k,{}).get("eligible_count")) for k in MARKETS),
                  "sampled_instruments":sum(_count(ready.get(k,{}).get("universe_size")) for k in MARKETS),
                  "outlook_status":"MARKET_REGIME_NOT_VALIDATED"},
        "horizons":horizons,
        "funds":{"growth_pick_count":len(fund_picks) if any(k in ready for k in FUNDS) else None,
                 "historical_watch_count":historical,
                 "ready_categories":sum(k in ready for k in FUNDS),"total_categories":len(FUNDS)},
        "institutional":flow,"news_headline_count":len(snapshot.get("recent_company_news") or []) if enabled else 0,
        "leading_evidence_gaps":[{"code":code,"watch_count":count} for code,count in
                                 sorted(blockers.items(),key=lambda x:(-x[1],x[0]))[:3]],
        "notice":"Deterministic briefing of current saved research, not a market forecast or AI consensus. Counts describe displayed evidence, not full-market coverage. Intraday and private portfolio assessments have separate workflows."}
