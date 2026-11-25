"""Conservative prospective watch monitoring and per-candidate evidence checks."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from statistics import mean, median
from zoneinfo import ZoneInfo
import json

from .watch_outcomes import HORIZONS, _table, OUTCOME_EVIDENCE_VERSION
from .replay_evidence import exact_isin
import re
from .horizon_research import VERSION

IST = ZoneInfo("Asia/Kolkata")
MIN_OUTCOMES = 30
MIN_IDENTITIES = 10
MIN_COVERAGE = .8
COHORT_DAYS = 365
MAX_ROWS = 5000
COSTS = (15, 30, 60)
NOTICE = ("Descriptive prospective watch outcomes, not independent trades or calibrated probabilities. "
          "Only current session-evidence outcomes enter metrics; legacy observations remain in the denominator. No index benchmark, point-in-time universe or verified execution. No recommendation gate is lifted.")

def _stamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("INVALID_TIMESTAMP")
    return dt.astimezone(IST).date()

def _finite(value):
    return type(value) in (int,float) and isfinite(value)

def _outcome(row, published, maturity, today):
    if row["status"] != "OBSERVED":
        return None
    outcome = json.loads(row["outcome"] or "{}")
    if (outcome.get("evidence_version")!=OUTCOME_EVIDENCE_VERSION or outcome.get("calendar_status")!="STORED_SESSIONS_MATCHED"
            or type(outcome.get("observations")) is not int or not 2<=outcome["observations"]<=500
            or not isinstance(outcome.get("history_fingerprint"),str) or not re.fullmatch(r"[0-9a-f]{64}",outcome["history_fingerprint"])):
        return None
    start,end = date.fromisoformat(outcome["entry_date"]),date.fromisoformat(outcome["exit_date"])
    a,b = outcome["entry_close"],outcome["exit_close"]
    if not (published<start<=published+timedelta(days=7) and maturity<=end<=maturity+timedelta(days=7)
            and start<=end<today and _finite(a) and _finite(b) and a>0 and b>0
            and isinstance(outcome.get("source_code"),str) and outcome["source_code"].strip()):
        return None
    result=b/a-1
    return result if isfinite(result) else None

def cohort(rows, horizon, today, truncated=False):
    # Select by publication and predeclared review dates, not by realized results.
    selected = []
    last_window = {}
    overlap = immature = incompatible = invalid = legacy_or_unverified = 0
    for row in rows:
        try:
            evidence=json.loads(row["evidence"])
            published=_stamp(row["published_at"])
            maturity=date.fromisoformat(row["maturity_date"])
            observed=date.fromisoformat(row["observed_date"])
            if evidence.get("methodology")!=VERSION or evidence.get("adjustment_status")!="ADJUSTED":
                incompatible+=1
                continue
            if (not 0<=(published-observed).days<=4 or maturity!=published+timedelta(days=HORIZONS[horizon])
                    or published>today or published<today-timedelta(days=COHORT_DAYS)):
                invalid+=1
                continue
            identity=evidence.get("isin")
            # Older publications without an exact ISIN cannot be reliably deduplicated across venues.
            if not exact_isin(identity):
                incompatible+=1
                continue
            if today<=maturity+timedelta(days=7):
                immature+=1
                continue
            if identity in last_window and published<=last_window[identity]:
                overlap+=1
                continue
            last_window[identity]=maturity+timedelta(days=7)
            try:
                change=_outcome(row,published,maturity,today)
            except (KeyError,ValueError,TypeError,OverflowError):
                change=None
            if row["status"]=="OBSERVED" and change is None:
                legacy_or_unverified+=1
            selected.append((identity,change,published))
        except (KeyError,ValueError,TypeError,OverflowError):
            invalid+=1
    outcomes=[x[1] for x in selected if x[1] is not None]
    identities=len({x[0] for x in selected if x[1] is not None})
    coverage=len(outcomes)/len(selected) if selected else 0
    metrics=[]
    for cost in COSTS:
        net=[(1+r)*(1-cost/10000)**2-1 for r in outcomes]
        if net:
            metrics.append({"cost_bps_per_side":cost,"mean_net_change_percent":round(mean(net)*100,4),
                "median_net_change_percent":round(median(net)*100,4),"positive_count":sum(r>0 for r in net),
                "negative_count":sum(r<0 for r in net),"flat_count":sum(r==0 for r in net)})
    blockers=[]
    if truncated:blockers.append("COHORT_LIMIT_REACHED")
    if len(outcomes)<MIN_OUTCOMES:blockers.append("INSUFFICIENT_MATURE_OUTCOMES")
    if identities<MIN_IDENTITIES:blockers.append("INSUFFICIENT_DISTINCT_IDENTITIES")
    if coverage<MIN_COVERAGE:blockers.append("INCOMPLETE_OUTCOME_COVERAGE")
    status="INSUFFICIENT_EVIDENCE" if blockers else "DESCRIPTIVE_SAMPLE_AVAILABLE"
    if not blockers and any(m["mean_net_change_percent"]<=0 for m in metrics):
        status="COST_SENSITIVE_OR_NEGATIVE_SAMPLE"
    return {"status":status,"methodology":VERSION,"horizon":horizon,"selected_mature_watches":len(selected),
        "observed_outcomes":len(outcomes),"distinct_observed_isins":identities,
        "coverage_percent":round(100*coverage,2),"overlap_excluded":overlap,
        "immature_excluded":immature,"incompatible_excluded":incompatible,"invalid_excluded":invalid,
        "legacy_or_unverified_observed":legacy_or_unverified,
        "cost_scenarios":metrics,"blockers":blockers,
        "notice":NOTICE}

def read(connect, instant=None):
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    with closing(connect()) as db:
        _table(db)
        results={}
        for horizon in HORIZONS:
            rows=db.execute("""SELECT * FROM watch_outcomes WHERE horizon=? AND published_at>=?
                ORDER BY published_at,instrument_id,observed_date LIMIT ?""",
                (horizon,(instant-timedelta(days=COHORT_DAYS+1)).isoformat(),MAX_ROWS+1)).fetchall()
            results[horizon]=cohort(rows[:MAX_ROWS],horizon,today,len(rows)>MAX_ROWS)
    return {"horizons":results,"notice":NOTICE}

def attach(snapshot, report, today):
    for section in snapshot.get("sections",[]):
        if not snapshot.get("enabled") or section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):
            continue
        for horizon in HORIZONS:
            group=(section.get("result") or {}).get("horizons",{}).get(horizon,{})
            for item in group.get("candidates",[]):
                blockers=list(group.get("blockers",[]))
                warnings=[]
                try:
                    age=(today-date.fromisoformat(item["as_of"])).days
                    if not 1<=age<=4:blockers.append("STALE_OR_INCOMPLETE_DAILY_OBSERVATION")
                except (KeyError,ValueError,TypeError):
                    blockers.append("INVALID_OBSERVATION_DATE")
                if item.get("adjustment_status")!="ADJUSTED":
                    blockers.append("ADJUSTED_PRICE_HISTORY_REQUIRED")
                company=item.get("company_evidence") or {}
                if not company.get("available_sections"):
                    blockers.append("COMPANY_EVIDENCE_UNAVAILABLE")
                else:
                    for trend in (company.get("financial_trends") or {}).get("items",[]):
                        if (trend.get("metric") in ("REVENUE","NET_PROFIT","OPERATING_CASH_FLOW")
                            and trend.get("latest_period_may_be_stale") is False
                            and (trend.get("direction")=="DECREASED" or (_finite(trend.get("latest_value")) and trend["latest_value"]<0))):
                            warnings.append(trend["metric"]+"_DETERIORATION_REVIEW")
                news=item.get("news_evidence") or {}
                if news.get("status") not in ("REVIEW_AVAILABLE","NO_RECENT_RETURNED_ARTICLES"):
                    blockers.append("CURRENT_NEWS_COVERAGE_UNAVAILABLE")
                if any("REGULATORY" in a.get("topics",[]) for a in news.get("articles",[])):
                    warnings.append("REGULATORY_HEADLINE_REVIEW")
                history=report.get("horizons",{}).get(horizon,{})
                blockers.extend(history.get("blockers",["PROSPECTIVE_MONITORING_UNAVAILABLE"]))
                if history.get("status")=="COST_SENSITIVE_OR_NEGATIVE_SAMPLE":
                    warnings.append("HISTORICAL_WATCH_SAMPLE_COST_SENSITIVE_OR_NEGATIVE")
                item["research_reliability"]={"status":"REVIEW_CONFLICTING_EVIDENCE" if warnings else "WATCH_ONLY_UNVALIDATED",
                    "blockers":sorted(set(blockers)),"warnings":sorted(set(warnings)),
                    "prospective_status":history.get("status","UNAVAILABLE"),
                    "notice":"Technical watch only. Evidence conflicts are review prompts, not confirmed adverse events or a calibrated prediction."}
    return snapshot


def attach_conclusions(snapshot):
    """A deterministic conclusion from the same current evidence shown in the report.

    Preserve every qualification blocker. Historical tests and AI commentary
    cannot promote a technical watch to an investment recommendation.
    """
    if not snapshot.get("enabled"):
        return snapshot
    for section in snapshot.get("sections",[]):
        if section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):
            continue
        for horizon in HORIZONS:
            group=(section.get("result") or {}).get("horizons",{}).get(horizon,{})
            for item in group.get("candidates",[]):
                reliability=item.get("research_reliability") or {}
                warnings=list(reliability.get("warnings",[]))
                blockers=sorted(set(group.get("blockers",[]))|set(reliability.get("blockers",[])))
                company=item.get("company_evidence") or {}
                quality=company.get("fundamental_quality") or {}
                warnings.extend(quality.get("warnings",[]))
                replay=item.get("matched_strategy_replay") or {}
                reviews=(item.get("ai_review") or {}).get("reviews",[])
                news=item.get("news_evidence") or {}
                trends=[t for t in (company.get("financial_trends") or {}).get("items",[])
                        if t.get("latest_period_may_be_stale") is False
                        and t.get("metric") in ("REVENUE","NET_PROFIT","OPERATING_CASH_FLOW")]
                replay_observed=replay.get("status")=="REPLAY_OBSERVED" and replay.get("as_of")==item.get("as_of")
                if replay_observed:
                    if any(_finite(c.get("net_return_percent")) and c["net_return_percent"]<=0 for c in replay.get("cost_scenarios",[])):
                        warnings.append("MATCHED_REPLAY_NONPOSITIVE_AFTER_COSTS")
                    if replay.get("small_sample") is True:
                        warnings.append("MATCHED_REPLAY_SMALL_SAMPLE")
                thesis="Technical watch meets the current horizon rules; a full investment verdict is withheld."
                if warnings:
                    thesis="Technical watch meets the current horizon rules, but risk or conflicting evidence requires review."
                conditions=["Reassess when the horizon-specific technical rules no longer pass.",
                            "Reassess on new financial results, material corporate events or changes in data quality."]
                if warnings:
                    conditions.append("Resolve the reported evidence concerns before reconsidering qualification.")
                if not replay_observed:
                    conditions.append("Obtain compatible same-instrument historical validation.")
                item["research_conclusion"]={
                    "status":"REVIEW_REQUIRED" if warnings else "WATCH_ONLY",
                    "summary":thesis,"blockers":blockers,"warnings":sorted(set(warnings)),
                    "evidence":{
                        "technical":"WATCH_RULES_MET",
                        "fundamentals":"REPORTED_TRENDS_AVAILABLE" if trends else "INCOMPLETE",
                        "news":"HEADLINES_AVAILABLE" if news.get("status")=="REVIEW_AVAILABLE" else
                               "NO_RETURNED_ARTICLES" if news.get("status")=="NO_RECENT_RETURNED_ARTICLES" else "UNAVAILABLE",
                        "historical_validation":"MATCHED_REPLAY_AVAILABLE" if replay_observed else "UNAVAILABLE",
                        "ai":"COMMENTARY_AVAILABLE" if reviews else "UNAVAILABLE",
                        "valuation":"SECTOR_COMPARISON_ONLY" if (quality.get("valuation") or {}).get("status")=="SECTOR_COMPARISON_ONLY" else "NOT_VERIFIED",
                        "peer_comparison":(company.get("peer_research") or {}).get("status","UNAVAILABLE"),
                        "business_quality":quality.get("status","UNAVAILABLE"),"institutional":"STOCK_LEVEL_NOT_VERIFIED",
                        "market_regime":"NOT_VALIDATED"},
                    "reassessment_conditions":conditions,
                    "notice":"Deterministic watch-only research conclusion; not a recommendation, target, stop-loss or calibrated probability."}
    return snapshot
