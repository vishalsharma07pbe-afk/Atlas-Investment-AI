"""Strict stock qualification report, distinct from existing technical watches.

Do not waive legacy blockers from descriptive evidence or AI agreement.
No source currently certifies live execution, independently dated fair value,
or prospective strategy qualification. Empty results describe reviewed samples,
not the whole market. Intraday remains in its separate live research workflow.
"""
from collections import Counter
from datetime import date
from math import isfinite
from .horizon_research import HORIZONS, MIN_HISTORY, BLOCKERS, VERSION as TECH_VERSION
from .replay_evidence import exact_isin
from . import stock_selection

VERSION="STOCK-QUALIFICATION-1"
NOTICE=("Strict evidence assessment of the already shortlisted daily watches only. Descriptive, reported and simulated evidence "
        "does not certify execution, independent fundamentals, valuation or prospective suitability. "
        "No model vote, technical score or partial evidence can override a missing mandatory gate. "
        "Zero qualified in this bounded reviewed sample does not establish that no market opportunity exists.")

def _num(v):
    return type(v) in (int,float) and isfinite(v)

def _codes(values):
    return {v for v in values if isinstance(v,str) and 0<len(v)<=180} if isinstance(values,list) else set()

def assess(item,group,coverage,context,horizon,today):
    gates=[]
    def gate(domain,available,requirements):
        remaining=sorted(set(requirements))
        gates.append({"domain":domain,"status":"PARTIAL_CONTEXT" if available and remaining else
                      "MISSING_EVIDENCE" if remaining else "OBSERVATION_CHECKS_MET",
                      "requirements":remaining})
    conclusion=item.get("research_conclusion") or {}
    reliability=item.get("research_reliability") or {}
    warnings=_codes(conclusion.get("warnings"))|_codes(reliability.get("warnings"))
    legacy=set(BLOCKERS[horizon])|_codes(group.get("blockers"))|_codes(conclusion.get("blockers"))|_codes(reliability.get("blockers"))
    exact=exact_isin(item.get("isin"))
    date_ok=False
    try:
        day=date.fromisoformat(item["as_of"])
        date_ok=(1<=(today-day).days<=4 and coverage.get("calendar_checked_on")==today.isoformat()
                 and coverage.get("calendar_status")=="PUBLISHED_SESSION" and coverage.get("expected_session")==day.isoformat())
    except (ValueError,TypeError,KeyError):
        pass
    technical=(group.get("status")=="TECHNICAL_WATCH_ONLY" and group.get("methodology")==TECH_VERSION
               and type(item.get("history_count")) is int and item["history_count"]>=MIN_HISTORY[horizon]
               and _num(item.get("rank_score")) and _num(item.get("close")) and item["close"]>0
               and _num(item.get("atr_percent")) and 0<item["atr_percent"]<=(5 if horizon=="SWING" else 4))
    requirements=[]
    if not exact:requirements.append("EXACT_STOCK_IDENTITY_REQUIRED")
    if not date_ok:requirements.append("CURRENT_EXPECTED_SESSION_REQUIRED")
    if not technical:requirements.append("CURRENT_HORIZON_TECHNICAL_RULES_REQUIRED")
    if item.get("adjustment_status")!="ADJUSTED":requirements.append("ADJUSTED_PRICE_HISTORY_REQUIRED")
    gate("TECHNICAL",technical,requirements)

    structure=item.get("price_structure") or {}
    geometry=structure.get("scenario") or {}
    geometric=(structure.get("as_of")==item.get("as_of") and structure.get("scenario_status")=="ILLUSTRATIVE_HISTORICAL_GEOMETRY"
               and _num(geometry.get("reward_to_risk")) and geometry["reward_to_risk"]>0)
    requirements=["LIVE_SPREAD_AND_EXECUTION_LIQUIDITY_REQUIRED","VALIDATED_EXECUTION_COSTS_REQUIRED"]
    if horizon=="SWING" and not geometric:requirements.append("BRACKETING_PRICE_STRUCTURE_REQUIRED")
    gate("EXECUTION_AND_RISK",geometric,requirements)

    company=item.get("company_evidence") or {}
    matched=exact and company.get("isin")==item["isin"]
    quality=company.get("fundamental_quality") or {} if matched else {}
    multi=quality.get("multi_year_quality") or {}
    fundamental=matched and multi.get("status")=="REPORTED_MULTI_YEAR_EVIDENCE" and bool(multi.get("metrics"))
    requirements=["INDEPENDENT_DATED_FILING_VERIFICATION_REQUIRED"]
    if not fundamental:requirements.append("MATCHED_MULTI_YEAR_FINANCIAL_HISTORY_REQUIRED")
    if horizon=="LONG_TERM":requirements.append("VERIFIED_BUSINESS_QUALITY_REQUIRED")
    gate("FUNDAMENTALS",fundamental,requirements)
    peer=(company.get("peer_research") or {}).get("valuation_research") or {} if matched else {}
    valuation=matched and peer.get("status")=="UNDATED_PEER_MULTIPLES" and bool(peer.get("metrics"))
    gate("VALUATION",valuation,["DATED_INTRINSIC_VALUATION_REQUIRED"] if horizon!="SWING" else ["VALUATION_AND_DOWNSIDE_CONTEXT_REQUIRED"])

    ownership=company.get("ownership_research") or {} if matched else {}
    gate("OWNERSHIP_AND_INSTITUTIONAL",matched and ownership.get("status")=="COMPARABLE_QUARTERS",
         ["STOCK_LEVEL_TRANSACTION_AND_PLEDGE_EVIDENCE_REQUIRED"])
    news=item.get("news_evidence") or {}
    gate("EVENT_RISK",news.get("status")=="REVIEW_AVAILABLE" and bool(news.get("articles")),
         ["VERIFIED_MATERIAL_EVENT_AND_RISK_ASSESSMENT_REQUIRED"])

    replay=item.get("matched_strategy_replay") or {}
    replay_ok=(replay.get("status")=="REPLAY_OBSERVED" and replay.get("as_of")==item.get("as_of")
               and type(replay.get("trades")) is int and replay["trades"]>0)
    requirements=["POINT_IN_TIME_EXECUTION_VALIDATION_REQUIRED"]
    if not replay_ok:requirements.append("MATCHED_SAME_STOCK_REPLAY_REQUIRED")
    else:
        if replay["trades"]<30:requirements.append("SUFFICIENT_HISTORICAL_SAMPLE_REQUIRED")
        costs=[r for r in replay.get("cost_scenarios",[]) if r.get("cost_bps_per_side")==30]
        if len(costs)!=1 or not _num(costs[0].get("net_return_percent")):requirements.append("COMPARABLE_AFTER_COST_REPLAY_REQUIRED")
        elif costs[0]["net_return_percent"]<=0:warnings.add("NONPOSITIVE_BASE_COST_REPLAY")
    gate("HISTORICAL_VALIDATION",replay_ok,requirements)
    prospective=reliability.get("prospective_status")=="DESCRIPTIVE_SAMPLE_AVAILABLE"
    gate("PROSPECTIVE_VALIDATION",prospective,["INDEPENDENT_PROSPECTIVE_STRATEGY_VALIDATION_REQUIRED"])

    regime=context.get("market_regime") or {}
    regime_ok=regime.get("status")=="OBSERVED_BENCHMARK_REGIME" and regime.get("as_of")==item.get("as_of")
    gate("MARKET_REGIME_AND_GLOBAL_CONTEXT",regime_ok,["VALIDATED_REGIME_SPECIFIC_STRATEGY_REQUIRED"])
    if regime_ok and regime.get("agreement")=="OPPOSING_DAILY_BREADTH_REVIEW":
        warnings.add("OPPOSING_DAILY_BREADTH_REVIEW")

    committee=(item.get("ai_review") or {}).get("committee") or {}
    audit=committee.get("claim_comparison") or {}
    checked=type(audit.get("matched_count")) is int and audit["matched_count"]>0
    if type(audit.get("contradicted_count")) is int and audit["contradicted_count"]>0:
        warnings.add("AI_ASSERTIONS_CONTRADICT_SUPPLIED_EVIDENCE")
    if type(audit.get("rejected_count")) is int and audit["rejected_count"]>0:
        warnings.add("AI_UNSUPPORTED_ASSERTIONS_WITHHELD")
    # AI is supplementary, not required to establish deterministic source truth.
    gates.append({"domain":"AI_COMMITTEE","status":"SUPPLEMENTARY_MATCHED_CLAIMS" if checked else "SUPPLEMENTARY_UNAVAILABLE",
                  "requirements":[]})
    all_blockers=legacy|{r for g in gates for r in g["requirements"]}
    # No current certified final qualification producer. Make that release
    # boundary explicit rather than implicitly promoting a watch.
    all_blockers.add("FINAL_QUALIFICATION_VALIDATION_REQUIRED")
    return {"methodology":VERSION,"status":"WITHHELD_REVIEW_REQUIRED" if warnings else "WITHHELD_EVIDENCE_GAPS",
            "horizon":horizon,"gates":gates,"blockers":sorted(all_blockers),
            "review_findings":sorted(warnings),"notice":NOTICE}

def attach(snapshot,today):
    report={"methodology":VERSION,"horizons":{},"notice":NOTICE}
    snapshot["stock_qualification"]=report
    enabled=snapshot.get("enabled") is True
    for horizon in HORIZONS:
        if horizon=="INTRADAY":
            report["horizons"][horizon]={"status":"SEPARATE_INTRADAY_WORKFLOW","reviewed_count":0,
                "review_required_count":0,"qualified_count":None,"recommendations":[],"leading_blockers":[],"notice":NOTICE}
            continue
        reviewed={}
        observations=[]
        groups=0
        ready_markets=set()
        for section in snapshot.get("sections",[]):
            market=section.get("section")
            if not enabled or market not in ("NSE","BSE") or section.get("status")!="READY":
                continue
            result=section.get("result") or {}
            group=(result.get("horizons") or {}).get(horizon)
            if not isinstance(group,dict):
                continue
            groups+=1
            ready_markets.add(market)
            for item in group.get("candidates",[]):
                if item.get("exchange")!=market or type(item.get("id")) is not int or item["id"]<=0:
                    continue
                decision=assess(item,group,result.get("discovery_coverage") or {},snapshot,horizon,today)
                item["stock_qualification"]=decision
                observations.append((item,decision))
                key=(market,item["id"])
                if key in reviewed:
                    # Duplicate observations must never inflate coverage.
                    continue
                reviewed[key]=decision
        selection=stock_selection.summarize(observations,ready_markets)
        counts=Counter(code for decision in reviewed.values() for code in decision["blockers"])
        report["horizons"][horizon]={"status":"DISABLED" if not enabled else
            "NO_QUALIFIED_IN_REVIEWED_SAMPLE" if reviewed else "NO_TECHNICAL_WATCHES" if groups else "AWAITING_RESEARCH",
            "reviewed_count":len(reviewed),"review_required_count":sum(bool(d["review_findings"]) for d in reviewed.values()),
            "qualified_count":0 if groups else None,"recommendations":[],
            "selection":selection,
            "leading_blockers":[{"code":k,"count":v} for k,v in sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:8]],
            "notice":NOTICE}
    return snapshot
