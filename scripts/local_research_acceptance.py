#!/usr/bin/env python3
"""Read-only acceptance of the running ATLAS research application.

Only loopback HTTP, no redirects, no environment proxies, no response dumps.
The interactive password and short-lived use of a session token stay in memory.
No registration, holdings mutation, forced refresh, provider call or trade.
"""
import argparse
from datetime import date,datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from math import isfinite
import getpass
import json
import re
import urllib.error
import urllib.request

SECTIONS={"NSE","BSE","LARGE_CAP","MID_CAP","SMALL_CAP","FLEXI_CAP","INDEX","LARGE_MID_CAP","MULTI_CAP","AGGRESSIVE_HYBRID","CORPORATE_BOND","SHORT_DURATION"}
SOURCES={"UPSTOX_REGISTRY","UPSTOX_DAILY_HISTORY","OFFICIAL_AMFI_NAV"}
BASES=("http://127.0.0.1:5173","http://127.0.0.1:8088")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class LocalSession:
    def __init__(self,base):
        if base not in BASES:raise ValueError("LOOPBACK_GATEWAY_REQUIRED")
        self.base=base
        self.token=None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def request(self,path,method="GET",body=None):
        headers={"Accept":"application/json","Origin":self.base,"Sec-Fetch-Site":"same-origin"}
        if self.token:headers["Authorization"]="Bearer "+self.token
        if body is not None:headers["Content-Type"]="application/json"
        request=urllib.request.Request(self.base+path,method=method,headers=headers,
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request,timeout=20) as response:
                raw=response.read(8_000_001)
                if len(raw)>8_000_000:raise ValueError("RESPONSE_TOO_LARGE")
                value=json.loads(raw)
                if not isinstance(value,dict):raise ValueError("INVALID_RESPONSE")
                return value
        except urllib.error.HTTPError as exc:
            raise RuntimeError("HTTP_"+str(exc.code)) from None
        except (OSError,ValueError) as exc:
            raise RuntimeError("LOCAL_RESPONSE_UNAVAILABLE") from None

def _portfolio_context_valid(context):
    """Validate the owner-local projection, not the upstream public status alone."""
    status=context.get("status")
    if status not in ("NO_CURRENT_WATCH_EVIDENCE","WATCH_CONTEXT_AVAILABLE",
                      "NO_NEW_EXACT_IDENTITY_WATCHES","DISABLED"):
        return False
    equities,funds=context.get("equities"),context.get("funds")
    excluded=context.get("held_excluded_count")
    if (not isinstance(equities,list) or not isinstance(funds,list)
        or type(excluded) is not int or excluded<0
        or any(not isinstance(row,dict) or row.get("evidence_type")!="TECHNICAL_WATCH_ONLY" for row in equities)
        or any(not isinstance(row,dict) or row.get("evidence_type")!="HISTORICAL_WATCH_ONLY" for row in funds)):
        return False
    if status=="WATCH_CONTEXT_AVAILABLE":
        return bool(equities or funds)
    return not equities and not funds

def assess(readiness,overview,review):
    """Return only allowlisted status labels, never private rows or raw errors."""
    checks={}
    def check(name,condition):
        checks[name]="PASS" if condition else "BLOCKED"

    sections=overview.get("sections")
    sections=sections if isinstance(sections,list) else []
    rows={r.get("section"):r for r in sections if isinstance(r,dict) and isinstance(r.get("section"),str)}
    check("scheduler_enabled",overview.get("enabled") is True and readiness.get("automatic_research_enabled") is True)
    check("all_research_sections_processed",len(sections)==len(SECTIONS) and set(rows)==SECTIONS and
          all(r.get("status")=="READY" and isinstance(r.get("result"),dict) for r in rows.values()))
    check("portfolio_review_contract",type(review.get("holding_count")) is int and review["holding_count"]>=0 and
          isinstance(review.get("holdings"),list) and len(review["holdings"])==review["holding_count"] and
          isinstance(review.get("diversification"),dict) and isinstance(review.get("opportunity_context"),dict) and
          _portfolio_context_valid(review["opportunity_context"]))
    check("research_only",readiness.get("actionable_recommendations_enabled") is False and
          overview.get("scope")=="PUBLIC_MARKET_RESEARCH_ONLY")
    runtime=all(v=="PASS" for v in checks.values())
    evidence=readiness.get("backend_evidence")
    evidence=evidence if isinstance(evidence,list) else []
    sources={r.get("code"):r for r in evidence if isinstance(r,dict) and isinstance(r.get("code"),str)}
    for code in sorted(SOURCES):
        row=sources.get(code,{})
        check(code,row.get("status")=="RECENT_LOCAL_EVIDENCE" and type(row.get("records")) is int and row["records"]>0)
    blockers=readiness.get("blockers")
    check("provider_declarations",readiness.get("provider_mode")=="UPSTOX" and isinstance(blockers,list) and
          not any(b in blockers for b in ("MARKET_DATA_USAGE_RIGHTS_NOT_CONFIRMED","MARKET_DATA_ENTITLEMENT_NOT_CONFIRMED")))
    check("equity_history_eligible",any(type(_obj(rows.get(key,{}).get("result")).get("eligible_count")) is int and
          (rows[key]["result"]["eligible_count"]>0) and rows[key].get("status")=="READY" for key in ("NSE","BSE")))
    check("fund_history_eligible",any(rows.get(key,{}).get("status")=="READY" and
          isinstance(rows[key].get("result"),dict) and
          isinstance(rows[key]["result"].get("historical_coverage"),dict) and
          rows[key]["result"]["historical_coverage"].get("status")=="HISTORICAL_WATCH_ONLY" and
          bool(rows[key]["result"]["historical_coverage"].get("items")) for key in SECTIONS-{"NSE","BSE"}))
    check("fresh_live_tick",readiness.get("live_market_data_connected") is True)
    return {"runtime":"PASS" if runtime else "BLOCKED",
            "stored_provider_evidence":"PASS" if all(checks[k]=="PASS" for k in SOURCES|{"provider_declarations","equity_history_eligible","fund_history_eligible"}) else "BLOCKED",
            "live_feed":"OBSERVED" if checks["fresh_live_tick"]=="PASS" else "NOT_OBSERVED",
            "checks":checks,"notice":"Stored evidence is not live connectivity or a qualified investment recommendation. No data or credentials are included."}

DAILY_HORIZONS=("SWING","SHORT_TERM","LONG_TERM")

def _obj(value):
    return value if isinstance(value,dict) else {}

def _list(value):
    return value if isinstance(value,list) else []

def _count(value):
    return type(value) is int and value>=0

def _ref(row):
    if not isinstance(row,dict):
        return None
    venue,identifier,isin=row.get("exchange"),row.get("id"),row.get("isin")
    if venue not in ("NSE","BSE") or type(identifier) is not int or identifier<=0 or not isinstance(isin,str) or len(isin)!=12:
        return None
    return venue,identifier,isin

def assess_workflows(readiness,overview,review,notifications):
    """Check the current product read contracts separately from actual source qualification.

    No output contains source rows, account identifiers, symbols, balances or
    untrusted values. Missing or inconsistent contracts fail closed.
    """
    checks={}
    def check(name,condition):
        checks[name]="PASS" if condition else "BLOCKED"

    sections={r["section"]:r for r in _list(overview.get("sections")) if isinstance(r,dict) and isinstance(r.get("section"),str)}
    ready={k:v for k,v in sections.items() if k in SECTIONS and v.get("status")=="READY" and isinstance(v.get("result"),dict)}
    briefing=_obj(overview.get("daily_briefing"))
    decision=_obj(briefing.get("decision_context"))
    pending=briefing.get("pending_sections")
    check("daily_briefing_contract",briefing.get("status")=="CURRENT_SECTIONS" and
          briefing.get("ready_sections")==len(ready)==len(SECTIONS) and briefing.get("total_sections")==len(SECTIONS)
          and pending==[] and isinstance(decision.get("review_companies"),list)
          and _count(decision.get("review_company_count"))
          and len(decision["review_companies"])<=min(5,decision["review_company_count"]))
    qualifications=_obj(_obj(overview.get("stock_qualification")).get("horizons"))
    decisions=_obj(decision.get("horizons"))
    canonical=True
    for horizon in DAILY_HORIZONS:
        report=_obj(qualifications.get(horizon))
        selected=_obj(report.get("selection"))
        shown=_obj(decisions.get(horizon))
        refs=selected.get("watch_refs")
        displayed=shown.get("selected_watches")
        if not isinstance(refs,list) or not isinstance(displayed,list) or len(refs)>5 or len(refs)!=len(displayed):
            canonical=False
            continue
        keys=[_ref(r) for r in refs]
        if None in keys or len({k[2] for k in keys if k is not None})!=len(keys) or [_ref(r) for r in displayed]!=keys:
            canonical=False
            continue
        for key,row in zip(keys,displayed):
            group=_obj(_obj(ready.get(key[0],{}).get("result")).get("horizons"))
            matches=[v for v in _list(_obj(group.get(horizon)).get("candidates")) if _ref(v)==key]
            if (len(matches)!=1 or not isinstance(row,dict) or row.get("as_of")!=matches[0].get("as_of")
                or _obj(matches[0].get("stock_qualification")).get("status") not in ("WITHHELD_REVIEW_REQUIRED","WITHHELD_EVIDENCE_GAPS")
                or not _obj(matches[0].get("stock_qualification")).get("blockers")):
                canonical=False
        # This release has no certified stock qualification producer.
        # Never equate an empty shortlist or a numeric score with qualification.
        if not (_count(report.get("qualified_count")) and report["qualified_count"]==0 and report.get("recommendations")==[] and shown.get("qualified_count")==0):
            canonical=False
    check("canonical_stock_report_contract",canonical and _obj(qualifications.get("INTRADAY")).get("status")=="SEPARATE_INTRADAY_WORKFLOW")
    fund_rows=[r["result"] for k,r in ready.items() if k not in ("NSE","BSE")]
    fund_contract=len(fund_rows)==len(SECTIONS)-2 and all(isinstance(r.get("top_performers"),list) and isinstance(r.get("growth_outlook"),list) for r in fund_rows)
    check("fund_qualification_contract",fund_contract and _obj(briefing.get("funds")).get("ready_categories")==len(fund_rows))
    check("portfolio_risk_contract",isinstance(review.get("portfolio_level_risk"),dict) and
          isinstance(review["portfolio_level_risk"].get("attention"),list))
    ids=notifications.get("ids")
    revisions=notifications.get("revision_keys")
    check("notification_summary_contract",isinstance(ids,list) and isinstance(revisions,list)
          and all(isinstance(x,str) and x for x in ids+revisions)
          and len(ids)==len(set(ids))==len(revisions)==len(set(revisions))==notifications.get("total")
          and notifications.get("research_history_status")=="AVAILABLE"
          and notifications.get("live_feed_connected") is False)
    jobs=_obj(readiness.get("research_jobs"))
    job_rows=[r for r in _list(jobs.get("jobs")) if isinstance(r,dict)]
    check("durable_alert_job_registered",jobs.get("status")=="PERSISTED_LOCAL_JOB_LEDGER" and
          sum(r.get("job")=="PUBLIC_RESEARCH_ALERTS" for r in job_rows)==1)
    # Product evidence is deliberately separate from API processing. A complete
    # source-backed qualification gate for stocks does not exist in this release.
    return {"workflow_runtime":"PASS" if all(v=="PASS" for v in checks.values()) else "BLOCKED",
            "checks":checks,"investment_qualification":"NOT_CERTIFIED",
            "notice":"Contract checks do not establish qualified picks, live execution, representative coverage or actual investment suitability."}

def assess_final_contracts(intraday,personal,journal,review):
    """Check read-only private and intraday surfaces; never certify investment picks."""
    intraday,personal,journal,review=map(_obj,(intraday,personal,journal,review))
    status=intraday.get("status")
    examined,eligible=intraday.get("examined"),intraday.get("eligible")
    candidates,warnings=intraday.get("candidates"),intraday.get("warnings")
    exchanges=intraday.get("open_exchanges")
    intraday_ok=(status in ("NOT_AUTHORIZED","SESSION_CLOSED_OR_UNVERIFIED","RESEARCH_ONLY")
        and _count(examined) and _count(eligible) and eligible<=examined
        and isinstance(exchanges,list) and all(x in ("NSE","BSE") for x in exchanges)
        and len(exchanges)==len(set(exchanges))
        and isinstance(candidates,list) and isinstance(warnings,list)
        and len(candidates)<=5 and len(warnings)<=5
        and len(candidates)+len(warnings)<=eligible
        and ((status=="RESEARCH_ONLY" and bool(exchanges)) or
             (status!="RESEARCH_ONLY" and not exchanges and examined==eligible==0 and candidates==warnings==[])))
    if intraday_ok:
        for rows,pattern in ((candidates,"VOLUME_BREAKOUT_WATCH"),(warnings,"FAILED_BREAKOUT_WATCH")):
            identities=set()
            for row in rows:
                if (not isinstance(row,dict) or row.get("pattern")!=pattern
                    or row.get("exchange") not in exchanges or type(row.get("id")) is not int
                    or row["id"]<=0 or not isinstance(row.get("bar_end"),str)
                    or any(row.get(k) is not None for k in ("target","stop_loss","recommendation"))):
                    intraday_ok=False
                    break
                key=(row["exchange"],row["id"])
                if key in identities:intraday_ok=False
                identities.add(key)
    # #297 adds exact company-level qualification to the existing endpoint.
    # Unknown qualification is not zero; a closed session cannot certify picks.
    q=_obj(intraday.get("qualification"))
    reviewed,required,qualified=q.get("reviewed_count"),q.get("review_required_count"),q.get("qualified_count")
    identified=q.get("unidentified_listing_count")
    cross=q.get("cross_venue_company_count")
    conflicts=q.get("conflicting_company_count")
    q_ok=(intraday_ok and all(_count(v) for v in (reviewed,required,identified,cross,conflicts))
        and required<=reviewed and conflicts<=required and cross<=reviewed
        and reviewed+identified<=eligible and q.get("recommendations")==[]
        and ((reviewed>0 and status=="RESEARCH_ONLY" and type(qualified) is int and qualified==0
              and q.get("status")=="NO_QUALIFIED_IN_REVIEWED_SAMPLE")
             or (reviewed==0 and qualified is None and q.get("status")==(
                 "NO_IDENTIFIED_TECHNICAL_WATCHES" if status=="RESEARCH_ONLY" else "AWAITING_RESEARCH")))
        and len(candidates)<=reviewed-required and len(warnings)<=required)
    if q_ok:
        seen=set()
        for row in candidates+warnings:
            isin=row.get("isin")
            decision=_obj(row.get("stock_qualification"))
            blocked=decision.get("blockers")
            findings=decision.get("review_findings")
            venues=row.get("observed_pattern_venues")
            if (not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or isin in seen
                or decision.get("horizon")!="INTRADAY"
                or decision.get("status") not in ("WITHHELD_EVIDENCE_GAPS","WITHHELD_REVIEW_REQUIRED")
                or not isinstance(blocked,list) or "FINAL_QUALIFICATION_VALIDATION_REQUIRED" not in blocked
                or not isinstance(findings,list) or bool(findings)!=(row["pattern"]=="FAILED_BREAKOUT_WATCH")
                or not isinstance(venues,list) or row["exchange"] not in venues
                or any(v not in exchanges for v in venues) or len(set(venues))!=len(venues)):
                q_ok=False
                break
            seen.add(isin)
    entries=journal.get("entries")
    journal_ok=isinstance(entries,list) and len(entries)<=200 and all(
        isinstance(e,dict) and isinstance(e.get("id"),str) and bool(e["id"])
        and e.get("status") in ("IDEA","RESEARCHING","MONITORING","CLOSED") for e in entries)
    if journal_ok:
        journal_ok=len({e["id"] for e in entries})==len(entries)
    checks={
        "intraday_watch_contract":"PASS" if intraday_ok and q_ok else "BLOCKED",
        "private_notification_summary":"PASS" if _count(personal.get("unread_count")) else "BLOCKED",
        "private_research_journal_contract":"PASS" if journal_ok else "BLOCKED",
    }
    populated=_count(review.get("holding_count")) and review["holding_count"]>0 and isinstance(review.get("holdings"),list) and len(review["holdings"])==review["holding_count"]
    return {"checks":checks,"final_runtime":"PASS" if all(v=="PASS" for v in checks.values()) else "BLOCKED",
        "populated_portfolio":"OBSERVED" if populated else "NOT_OBSERVED",
        "intraday_evidence":"OBSERVED" if intraday_ok and q_ok and status=="RESEARCH_ONLY" and eligible>0 else "NOT_OBSERVED",
        "product_acceptance":"NOT_CERTIFIED",
        "remaining_acceptance":["AUTHORIZED_SOURCE_COVERAGE","QUALIFIED_INVESTMENT_RESEARCH",
            "POPULATED_PORTFOLIO_ACCURACY","ACTUAL_LOCAL_UPGRADE_AND_RECOVERY",
            "REPRESENTATIVE_RESOURCE_AND_UX_VERIFICATION","ACTUAL_LOCAL_PRIVACY_VERIFICATION"]}

STOCK_DOMAINS=("TECHNICAL","EXECUTION_AND_RISK","FUNDAMENTALS","VALUATION",
    "OWNERSHIP_AND_INSTITUTIONAL","EVENT_RISK","HISTORICAL_VALIDATION",
    "PROSPECTIVE_VALIDATION","MARKET_REGIME_AND_GLOBAL_CONTEXT","AI_COMMITTEE")
FUND_GATES=frozenset(("OFFICIAL_CATEGORY","EXACT_DIRECT_GROWTH_PLAN",
    "CATEGORY_SPECIFIC_RISK_MODEL_REQUIRED","CATEGORY_STRATEGY_MISMATCH","FRESH_DATED_NAV",
    "OFFICIAL_RISKOMETER","THREE_YEAR_NAV_HISTORY","EXPENSE_RATIO","UNDERLYING_INDEX",
    "TRACKING_DIFFERENCE","TRACKING_ERROR","ONE_YEAR_RETURN","THREE_YEAR_RETURN",
    "PEER_PERCENTILE","BENCHMARK_HIT_RATE","WORST_ROLLING_RETURN","MAX_DRAWDOWN",
    "VOLATILITY","RECENT_PORTFOLIO_DISCLOSURE","PORTFOLIO_COVERAGE_80_PERCENT",
    "INDEX_OUTLOOK_COVERAGE_70_PERCENT","EARNINGS_COVERAGE_70_PERCENT",
    "VALUATION_COVERAGE_60_PERCENT","FORWARD_EARNINGS_GROWTH","VALUATION_EVIDENCE",
    "SECTOR_DRIVERS","CONCENTRATION","LIQUIDITY","DUPLICATE_SCHEME_IDENTITY",
    "SELECTED_HORIZON_OR_RISK_REVIEW_REQUIRED"))
STOCK_GATE_STATES=("PARTIAL_CONTEXT","MISSING_EVIDENCE","OBSERVATION_CHECKS_MET",
                   "SUPPLEMENTARY_MATCHED_CLAIMS","SUPPLEMENTARY_UNAVAILABLE")

def _bounded_count(value,maximum=1000000):
    return value if _count(value) and value<=maximum else None

def _distinct_stock_count(rows,maximum):
    if not isinstance(rows,list) or len(rows)>maximum:
        return None
    refs=[_ref(row) for row in rows]
    if any(ref is None or not re.fullmatch(r"INE[A-Z0-9]{9}",ref[2]) for ref in refs):
        return None
    return len(refs) if len({ref[2] for ref in refs})==len(refs) else None

def qualification_audit(overview,readiness=None,intraday=None):
    """Aggregate existing public evidence; never echo identifiers or unknown strings.

    A missing gate is not a passed gate. Audit coverage is separate from certification.
    """
    section_rows=_list(overview.get("sections"))
    def section(key):
        matches=[r for r in section_rows if isinstance(r,dict) and r.get("section")==key]
        return _obj(matches[0].get("result")) if len(matches)==1 and matches[0].get("status")=="READY" else {}
    stocks={}
    reports=_obj(_obj(overview.get("stock_qualification")).get("horizons"))
    reliability=_obj(_obj(overview.get("research_reliability")).get("horizons"))
    for horizon in DAILY_HORIZONS:
        report=_obj(reports.get(horizon))
        domains={domain:{state:0 for state in STOCK_GATE_STATES}|{"UNKNOWN":0} for domain in STOCK_DOMAINS}
        coverage={}
        for venue in ("NSE","BSE"):
            result=section(venue)
            group=_obj(_obj(result.get("horizons")).get(horizon))
            candidates=group.get("candidates")
            coverage[venue]={"eligible_history_count":_bounded_count(result.get("eligible_count")),
                             "horizon_eligible_histories":_bounded_count(_obj(_obj(result.get("history_coverage")).get(horizon)).get("eligible_histories")),
                             "watch_rows":len(candidates) if isinstance(candidates,list) and len(candidates)<=100 else None}
            if coverage[venue]["watch_rows"] is None:
                continue
            seen=set()
            for item in candidates:
                key=_ref(item)
                if key is None or key[0]!=venue or key in seen:
                    continue
                seen.add(key)
                decision=_obj(item.get("stock_qualification"))
                gates=_list(decision.get("gates"))
                for domain in STOCK_DOMAINS:
                    matched=[g for g in gates if isinstance(g,dict) and g.get("domain")==domain]
                    state=matched[0].get("status") if len(matched)==1 else None
                    domains[domain][state if state in STOCK_GATE_STATES else "UNKNOWN"]+=1
        prospective=_obj(reliability.get(horizon))
        selection=_obj(report.get("selection"))
        stocks[horizon]={"strict_watch_count":_distinct_stock_count(selection.get("watch_refs"),5),
            "preliminary_watch_count":_distinct_stock_count(selection.get("preliminary_watch_refs"),5),
            "market_coverage":coverage,"reviewed_count":_bounded_count(report.get("reviewed_count")),
            "qualified_count":_bounded_count(report.get("qualified_count")),"domain_counts":domains,
            "prospective_mature_watches":_bounded_count(prospective.get("selected_mature_watches")),
            "prospective_observed_outcomes":_bounded_count(prospective.get("observed_outcomes")),
            "prospective_distinct_isins":_bounded_count(prospective.get("distinct_observed_isins")),
            "prospective_matched_benchmark_outcomes":_bounded_count(_obj(prospective.get("benchmark_summary")).get("matched_outcomes")),
            "prospective_close_paths":_bounded_count(_obj(prospective.get("risk_path_summary")).get("observed_paths")),
            "historical_replay_observed_instruments":_bounded_count(_obj(_obj(_obj(overview.get("strategy_validation")).get("horizons")).get(horizon)).get("observed_instruments"))}
    funds={}
    for category in sorted(SECTIONS-{"NSE","BSE"}):
        result=section(category)
        historical=_obj(result.get("historical_coverage"))
        summary=_obj(result.get("qualification_counts"))
        evaluated=_bounded_count(summary.get("evaluated_count"),40)
        top=_bounded_count(summary.get("top_eligible_count"),40)
        growth=_bounded_count(summary.get("growth_eligible_count"),40)
        valid=evaluated is not None and top is not None and growth is not None and max(top,growth)<=evaluated
        def gap_counts(field,eligible):
            values=summary.get(field)
            if not valid or not isinstance(values,dict):
                return None
            withheld=evaluated-eligible
            if any(k not in FUND_GATES|{"UNKNOWN_GATE"} or type(v) is not int or not 1<=v<=withheld for k,v in values.items()):
                return None
            if (not withheld and values) or (withheld and sum(values.values())<withheld):
                return None
            return dict(values)
        shortlist=_obj(result.get("historical_research_shortlist"))
        rows=shortlist.get("items")
        historical_watch_count=None
        if isinstance(rows,list) and len(rows)<=5 and all(isinstance(row,dict) and
                row.get("qualified") is False and row.get("status")=="HISTORICAL_RESEARCH_ONLY" and
                isinstance(row.get("identifier"),str) and re.fullmatch(r"[1-9][0-9]{5,8}",row["identifier"])
                for row in rows) and len({row["identifier"] for row in rows})==len(rows):
            historical_watch_count=len(rows)
        funds[category]={"historical_research_watch_count":historical_watch_count,
            "history_sample_count":_bounded_count(historical.get("sample_count"),40),
            "history_eligible_count":_bounded_count(historical.get("eligible_count"),40),
            "evaluated_count":evaluated if valid else None,"top_eligible_count":top if valid else None,
            "growth_eligible_count":growth if valid else None,
            "top_missing_gate_counts":gap_counts("top_missing_gate_counts",top),
            "growth_missing_gate_counts":gap_counts("growth_missing_gate_counts",growth)}
    acquisition=_obj(_obj(_obj(readiness).get("research_jobs")).get("company_acquisition"))
    count_keys=("never_attempted","available","partial","unavailable","running","fresh_reports",
                "fresh_current_normalization","legacy_reports","due_legacy_reports")
    sample=_bounded_count(acquisition.get("sample_identities"),40000)
    company_counts={k:_bounded_count(_obj(acquisition.get("counts")).get(k),sample or 0)
                    for k in count_keys} if sample is not None else {k:None for k in count_keys}
    sections=("profile","ratios","income_statement","balance_sheet","cash_flow","shareholding","corporate_actions","competitors")
    company_audit={"sample_identities":sample,"due_sample":_bounded_count(acquisition.get("due_sample"),sample or 0) if sample is not None else None,
        "annual_archive_companies":_bounded_count(acquisition.get("annual_archive_companies"),sample or 0) if sample is not None else None,
        "counts":company_counts,
        "fresh_sections":{k:_bounded_count(_obj(acquisition.get("fresh_sections")).get(k),sample or 0) if sample is not None else None for k in sections}}
    q=_obj(_obj(intraday).get("qualification"))
    stocks["INTRADAY"]={k:_bounded_count(q.get(k)) for k in ("reviewed_count","review_required_count","qualified_count","unidentified_listing_count","cross_venue_company_count","conflicting_company_count")}
    screen=_obj(overview.get("steady_momentum"))
    strict=_obj(screen.get("strict_suggestions"))
    displayed=_distinct_stock_count(strict.get("items"),10)
    matched=_bounded_count(strict.get("matched_count"))
    if strict.get("qualification_eligible") is not False or displayed is None or matched is None or displayed!=min(matched,10) or strict.get("status")!=("JOINT_SCREEN_MATCHES" if matched else "NO_JOINT_SCREEN_MATCHES"):
        displayed=matched=None
    reported=_obj(screen.get("reported_suggestions"))
    reported_displayed=_distinct_stock_count(reported.get("items"),10)
    reported_matched=_bounded_count(reported.get("matched_count"))
    if reported.get("qualification_eligible") is not False or reported_displayed is None or reported_matched is None or reported_displayed!=min(reported_matched,10) or reported.get("status")!=("REPORTED_JOINT_MATCHES" if reported_matched else "NO_REPORTED_JOINT_MATCHES"):
        reported_displayed=reported_matched=None
    elite={"strict_joint_match_count":matched,"displayed_strict_suggestion_count":displayed,
           "reported_joint_match_count":reported_matched,"displayed_reported_suggestion_count":reported_displayed,
           "preliminary_business_match_count":_bounded_count(screen.get("matched_count"))}
    return {"status":"EVIDENCE_AUDIT_ONLY","stocks":stocks,"funds":funds,"elite":elite,"company_acquisition":company_audit,
            "notice":"Counts describe bounded existing snapshots; null means unavailable, not zero. No new data acquisition, investment recommendation or certification."}

ADVANCED_JOBS=("OFFICIAL_TRI_DOWNLOAD","OFFICIAL_AMC_FACTSHEETS","NSE_FINANCIAL_FILINGS",
    "FUND_AI_REVIEW","FUND_WATCH_OUTCOMES","FORWARD_EARNINGS_BASELINE","WATCH_OUTCOMES","STRATEGY_REPLAY")
def advanced_audit(readiness,overview,review,intraday):
    """Read-only bounded aggregate acceptance; distinguish contracts from evidence.
    No user rows, provider URLs, raw messages, IDs, symbols or money in output.
    """
    checks={};evidence={}
    def check(k,v):checks[k]="PASS" if v else "BLOCKED"
    d=_obj(overview.get("unified_decision"))
    companies=d.get("equity_companies")
    seen=set();observations=set();reviews=ai_count=0
    ok=(d.get("methodology")=="UNIFIED-DECISION-1" and d.get("status") in ("RESEARCH_CONTEXT_AVAILABLE","AWAITING_EVIDENCE")
        and isinstance(companies,list) and len(companies)<=55)
    if ok:
        for c in companies:
            c=_obj(c);isin=c.get("isin");rows=c.get("observations")
            if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or isin in seen or c.get("qualified") is not False or not isinstance(rows,list) or not rows or len(rows)>20:
                ok=False;break
            seen.add(isin);required=reviewed=False
            for row in rows:
                row=_obj(row);key=_ref(row);h=row.get("horizon")
                if key is None or key[2]!=isin or h not in (*DAILY_HORIZONS,"ELITE") or (h,key) in observations or row.get("qualified") is not False or row.get("state") not in ("WATCH_ONLY","REVIEW_REQUIRED") or "FINAL_QUALIFICATION_VALIDATION_REQUIRED" not in _list(row.get("blockers")):
                    ok=False;break
                observations.add((h,key));required=required or row["state"]=="REVIEW_REQUIRED"
                count=_obj(row.get("ai")).get("reviewed_count")
                if count is not None and (type(count) is not int or not 1<=count<=5):ok=False;break
                reviewed=reviewed or count is not None
            if c.get("state")!=("REVIEW_REQUIRED" if required else "WATCH_ONLY") or c.get("ai_reviewed") is not reviewed:ok=False
            reviews+=required;ai_count+=reviewed
        counts=(d.get("equity_company_count"),d.get("equity_review_count"),d.get("ai_reviewed_company_count"))
        ok=ok and (counts==(len(companies),reviews,ai_count) or not companies and counts==(None,None,None))
    # Compare the projection with actual canonical selection, not its self-reported count.
    canonical=set();canonical_ok=True
    reports=_obj(_obj(overview.get("stock_qualification")).get("horizons"))
    for horizon in DAILY_HORIZONS:
        refs=_obj(_obj(reports.get(horizon)).get("selection")).get("watch_refs")
        if not isinstance(refs,list) or len(refs)>5:
            canonical_ok=False;continue
        keys=[_ref(r) for r in refs]
        if any(k is None for k in keys) or len(set(keys))!=len(keys):
            canonical_ok=False;continue
        canonical.update((horizon,key) for key in keys)
    projected={x for x in observations if x[0]!="ELITE"}
    check("canonical_decision_projection",canonical_ok and canonical==projected and
          d.get("canonical_projection_complete") is True and d.get("missing_canonical_watch_count")==0)
    check("unified_equity_decisions",ok)
    evidence["unified_company_count"]=_bounded_count(d.get("equity_company_count"),55) if ok else None
    evidence["ai_reviewed_company_count"]=_bounded_count(d.get("ai_reviewed_company_count"),55) if ok else None
    funds=d.get("fund_categories");seen_categories=set()
    fund_ok=isinstance(funds,list) and len(funds)<=len(SECTIONS)-2
    if fund_ok:
        for f in funds:
            f=_obj(f);cat=f.get("category");w=f.get("historical_watches")
            if cat not in SECTIONS-{"NSE","BSE"} or cat in seen_categories or not isinstance(w,list) or len(w)>5 or any(_obj(row).get("qualified") is not False for row in w):
                fund_ok=False;break
            seen_categories.add(cat)
            counts=[f.get(k) for k in ("reviewed_count","top_withheld_count","growth_withheld_count")]
            if not (all(x is None for x in counts) or all(_count(x) for x in counts) and max(counts[1:])<=counts[0]<=40):
                fund_ok=False;break
    check("unified_fund_decisions",fund_ok)
    holdings=review.get("holdings");summary=_obj(review.get("portfolio_reassessment"))
    portfolio_ok=isinstance(holdings,list) and _count(review.get("holding_count")) and review["holding_count"]==len(holdings)
    states={"REVIEW_REQUIRED":0,"WATCH_ONLY":0,"AWAITING_EVIDENCE":0}
    scored=0
    if portfolio_ok:
        for holding in holdings:
            h=_obj(holding);decision=_obj(h.get("unified_decision"));a=_obj(h.get("reassessment"));state=decision.get("state")
            mapping={"REASSESS_EVIDENCE":"REVIEW_REQUIRED","MONITOR_RESEARCH_ONLY":"WATCH_ONLY","COLLECT_EVIDENCE":"AWAITING_EVIDENCE"}
            if decision.get("scope")!="OWNER_LOCAL" or decision.get("methodology")!="UNIFIED-DECISION-1" or decision.get("qualified") is not False or a.get("qualified") is not False or state not in states or mapping.get(a.get("review_state"))!=state:
                portfolio_ok=False;break
            states[state]+=1
            score=a.get("score")
            if score is not None:
                if type(score) not in (int,float) or not 0<=score<=100 or a.get("status")!="PRELIMINARY_SCORE_ONLY":portfolio_ok=False;break
                scored+=1
            elif a.get("status")!="SCORE_WITHHELD":portfolio_ok=False;break
        portfolio_ok=portfolio_ok and summary.get("holding_count")==len(holdings) and summary.get("scored_count")==scored and summary.get("reassess_count")==states["REVIEW_REQUIRED"] and summary.get("monitor_count")==states["WATCH_ONLY"] and summary.get("evidence_needed_count")==states["AWAITING_EVIDENCE"]
    check("owner_local_reassessment",portfolio_ok)
    evidence["populated_portfolio_contract"]="OBSERVED" if portfolio_ok and holdings else "NOT_OBSERVED"
    session=_obj(intraday.get("unified_decision"))
    check("intraday_decision_scope",session.get("methodology")=="UNIFIED-DECISION-1" and session.get("scope")=="CURRENT_SESSION" and session.get("qualified") is False and session.get("state") in states)
    jobs=_list(_obj(readiness.get("research_jobs")).get("jobs"))
    check("advanced_jobs_registered",all(sum(_obj(j).get("job")==name for j in jobs)==1 for name in ADVANCED_JOBS))
    evidence["jobs"]={name:next((_obj(j).get("status") for j in jobs if _obj(j).get("job")==name and _obj(j).get("status") in ("PENDING","RUNNING","PASS_COMPLETED","WAITING_EVIDENCE","FAILED","DISABLED_OR_NOT_AUTHORIZED","INTERRUPTED")),None) for name in ADVANCED_JOBS}
    forward=_obj(overview.get("forward_earnings_validation"))
    check("forward_validation_contract",forward.get("methodology")=="QUARTER-PERSISTENCE-1" and forward.get("calibrated") is False and forward.get("status") in ("DISABLED_OR_NOT_AUTHORIZED","AWAITING_PUBLICATIONS","PROSPECTIVE_EXPERIMENT") and isinstance(forward.get("quarter_cohorts"),list))
    evidence["pending_earnings_publications"]=_bounded_count(forward.get("pending_count"),5000)
    calibration=_obj(overview.get("score_calibration"));horizons=_obj(calibration.get("horizons"))
    check("temporal_validation_contract",calibration.get("calibrated") is False and all(_obj(_obj(horizons.get(h)).get("temporal_diagnostics")).get("calibrated") is False for h in DAILY_HORIZONS))
    sources={}
    for section in _list(overview.get("sections")):
        section=_obj(section);cat=section.get("section")
        if cat not in SECTIONS-{"NSE","BSE"} or section.get("status")!="READY":continue
        r=_obj(section.get("result"));tri=_obj(r.get("official_tri_coverage"));amc=_obj(r.get("official_amc_coverage"))
        sources[cat]={"tri_available_count":_bounded_count(tri.get("available_count"),20),
                      "amc_matched_schemes":_bounded_count(amc.get("matched_schemes"),40)}
    evidence["official_fund_sources"]=sources
    return {"status":"PASS" if all(v=="PASS" for v in checks.values()) else "BLOCKED","checks":checks,
            "observed_evidence":evidence,"investment_qualification":"NOT_CERTIFIED",
            "notice":"Contract audit only. Empty or disabled evidence is not a verified provider or investment result."}

RECOVERY_FIELDS=("current_listings","deep_listings","adjusted_depth_listings","recoverable_missing","due_missing")
RECOVERY_COUNTS=("mapped_listings","mapped_companies","active_claims","expired_claims","failed_last_attempts","never_attempted","suspended_listings","protected_adjusted_listings")
GLOBAL_PUBLISHERS=("FRED","EIA","US_TREASURY","TWELVE_DATA","ECB","FED","BLS")
COMPANY_SECTIONS=("profile","ratios","income_statement","quarterly_income","balance_sheet","cash_flow","shareholding","corporate_actions","competitors")
def _date(value):
    try:
        day=date.fromisoformat(value)
        return day if day.isoformat()==value else None
    except (ValueError,TypeError):return None

def _timestamp(value):
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
        return stamp if stamp.tzinfo is not None else None
    except (ValueError,TypeError,AttributeError,OverflowError):return None

def recovery_audit(history,readiness,overview,providers,instant=None):
    """Validate aggregate contracts, not evidence sufficiency or source rights.

    Fixed output fields only: do not echo labels, symbols, provider messages,
    URLs, account data or credential/configuration values.
    """
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    history,readiness,overview,providers=map(_obj,(history,readiness,overview,providers))
    checks={};evidence={}
    def check(name,ok):checks[name]="PASS" if ok else "BLOCKED"
    rows=history.get("exchanges");market={}
    stamp=_timestamp(history.get("generated_at"))
    history_ok=(isinstance(rows,list) and len(rows)==2 and type(history.get("configured")) is bool
        and type(history.get("provider_blocked")) is bool and history.get("depth_target")==253
        and stamp is not None and abs((instant-stamp).total_seconds())<=300
        and _count(history.get("distinct_mapped_companies")))
    if history_ok:
        for row in rows:
            row=_obj(row);venue=row.get("exchange");mapped=row.get("mapped_listings")
            if venue not in ("NSE","BSE") or venue in market or not _count(mapped) or any(not _count(row.get(k)) or row[k]>mapped for k in RECOVERY_COUNTS):
                history_ok=False;break
            target=_date(row.get("target_session"))
            known=row.get("calendar_status")=="VERIFIED_PRIOR_REGULAR_SESSION"
            if known:
                if not target or not 1<=(today-target).days<=14 or any(not _count(row.get(k)) or row[k]>mapped for k in RECOVERY_FIELDS):
                    history_ok=False;break
                if not (row["due_missing"]<=row["recoverable_missing"]<=mapped-row["current_listings"] and row["adjusted_depth_listings"]<=row["deep_listings"]):
                    history_ok=False;break
            elif row.get("calendar_status")!="UNVERIFIED" or row.get("target_session") is not None or any(row.get(k) is not None for k in RECOVERY_FIELDS):
                history_ok=False;break
            market[venue]={"target_session":target.isoformat() if known else None,**{k:row.get(k) for k in RECOVERY_COUNTS+RECOVERY_FIELDS}}
        if history_ok:
            counts=[v["mapped_companies"] for v in market.values()]
            history_ok=max(counts)<=history["distinct_mapped_companies"]<=sum(counts)
    check("history_recovery_contract",history_ok)
    evidence["history"]={"exchanges":market,"configured":history["configured"],"provider_blocked":history["provider_blocked"],
        "distinct_mapped_companies":history["distinct_mapped_companies"]} if history_ok else None

    jobs=_obj(readiness.get("research_jobs"))
    company=_obj(jobs.get("company_acquisition"));sample=company.get("sample_identities")
    company_ok=company.get("status")=="DISABLED_OR_NOT_AUTHORIZED"
    company_evidence=None
    if company.get("status")=="LOCAL_ACQUISITION_AUDIT":
        counts=_obj(company.get("counts"));primary=company.get("primary_identities")
        fip=company.get("fip_priority_identities");due=company.get("due_fip_priority")
        company_ok=(all(_count(v) for v in (sample,primary,fip,due,company.get("due_sample"),company.get("due_primary")))
            and fip<=10 and due<=fip<=primary and company["due_sample"]<=sample and company["due_primary"]<=primary
            and type(company.get("global_company_cooldown")) is bool
            and all(_count(counts.get(k,0)) and counts.get(k,0)<=sample for k in ("fresh_reports","fresh_current_normalization","incremental_reports")))
        if company_ok:
            company_evidence={"sample_identities":sample,"primary_identities":primary,"fip_priority_identities":fip,"due_fip_priority":due,
                "fresh_reports":counts.get("fresh_reports",0),"incremental_reports":counts.get("incremental_reports",0)}
            company_ok=company_evidence["incremental_reports"]<=company_evidence["fresh_reports"]<=sample
    check("company_recovery_contract",company_ok)
    evidence["company"]=company_evidence if company_ok else None

    funds=_obj(jobs.get("fund_disclosure_acquisition"))
    fund_ok=funds.get("status") in ("DISABLED_OR_NOT_AUTHORIZED","NO_SNAPSHOT")
    fund_evidence=None
    if funds.get("status") in ("LAST_SUCCESSFUL_SECONDARY_FILE","STALE_SECONDARY_FILE"):
        total=funds.get("stored_scheme_count");fields=_obj(funds.get("fresh_field_counts"))
        allowed=("aum_cr_all_plans","benchmark","riskometer","ter_percent","base_expense_percent","fund_managers","exit_load")
        fund_ok=(_count(total) and total>0 and isinstance(funds.get("source_counts"),dict)
                 and isinstance(funds.get("fresh_field_counts"),dict) and all(k in allowed and _count(v) and v<=total for k,v in fields.items())
                 and (funds["status"]!="STALE_SECONDARY_FILE" or not fields))
        if fund_ok:fund_evidence={"stored_scheme_count":total,"fresh_field_counts":{k:fields[k] for k in allowed if k in fields},
                                  "fresh_snapshot":funds["status"]=="LAST_SUCCESSFUL_SECONDARY_FILE"}
    check("fund_disclosure_recovery_contract",fund_ok)
    evidence["fund_disclosures"]=fund_evidence

    global_state=_obj(jobs.get("global_source_recovery"));global_rows=global_state.get("providers")
    global_ok=global_state.get("status")=="PERSISTED_GLOBAL_RECOVERY" and isinstance(global_rows,list) and len(global_rows)==len(GLOBAL_PUBLISHERS)
    states={}
    if global_ok:
        for row in global_rows:
            row=_obj(row);key=row.get("provider");state=row.get("state")
            if key not in GLOBAL_PUBLISHERS or key in states or state not in ("CLOSED","NOT_OBSERVED","OPEN","PROBE_IN_PROGRESS","RECOVERY_PROBE_DUE") or not _count(row.get("retry_after_seconds")):
                global_ok=False;break
            states[key]=state
    check("global_recovery_contract",global_ok)
    evidence["global_publishers"]=states if global_ok else None

    fallback=_obj(providers.get("fallback_observation"));n=fallback.get("observation_count")
    fallback_ok=(providers.get("automatic_fallback_available") is False and providers.get("streaming_verified") is False
        and type(providers.get("same_market_fallback_configured")) is bool and fallback.get("route")=="UPSTOX_TO_DHAN"
        and _count(n) and ((fallback.get("status")=="NOT_OBSERVED" and n==0 and fallback.get("last_observed_at") is None)
             or (fallback.get("status")=="PAST_VALIDATED_HTTP_FALLBACK" and n>0 and _timestamp(fallback.get("last_observed_at")) is not None)))
    check("fallback_provenance_contract",fallback_ok)
    evidence["fallback"]={"configured":providers["same_market_fallback_configured"],"past_observation_count":n} if fallback_ok else None

    archive=overview.get("historical_display");seen=set();total=0
    archive_ok=isinstance(archive,list) and len(archive)<=len(SECTIONS)
    section_rows={r.get("section"):r for r in _list(overview.get("sections")) if isinstance(r,dict) and isinstance(r.get("section"),str)}
    if archive_ok:
        for row in archive:
            row=_obj(row);key=row.get("section");observations=row.get("observations");stamp=_timestamp(row.get("generated_at"))
            equity=key in ("NSE","BSE")
            if (key not in SECTIONS or key in seen or row.get("status")!="HISTORICAL_DISPLAY_ONLY" or row.get("qualification_eligible") is not False
                or overview.get("enabled") is not True or row.get("current_status") not in ("READY","STALE","FAILED")
                or row.get("current_status")!=_obj(section_rows.get(key)).get("status")
                or row.get("metric")!=("20_SESSION_PRICE_CHANGE" if equity else "3_YEAR_CAGR")
                or stamp is None or not timedelta(0)<=instant-stamp<=timedelta(days=7)
                or not isinstance(observations,list) or not 1<=len(observations)<=5):
                archive_ok=False;break
            for item in observations:
                item=_obj(item);day=_date(item.get("observed_date"));value=item.get("value_percent")
                if (set(item)!={"label","observed_date","value_percent"} or not isinstance(item.get("label"),str)
                    or not 1<=len(item["label"])<=300 or day is None or not (1 if equity else 0)<=(stamp.astimezone(ZoneInfo("Asia/Kolkata")).date()-day).days<=(4 if equity else 7)
                    or type(value) not in (int,float) or not isfinite(value) or abs(value)>1e6):
                    archive_ok=False;break
            if not archive_ok:break
            seen.add(key);total+=len(observations)
    check("historical_display_isolation_contract",archive_ok)
    evidence["historical_display"]={"section_count":len(seen),"observation_count":total} if archive_ok else None
    return {"status":"PASS" if all(v=="PASS" for v in checks.values()) else "BLOCKED","checks":checks,
            "observed_evidence":evidence,"product_acceptance":"NOT_CERTIFIED",
            "notice":"Recovery contracts only. Unknown calendars, empty archives, disabled optional sources and zero observations are not evidence of working live acquisition."}

def collect(request,include_qualification_audit=False,include_advanced_audit=False,include_recovery_audit=False):
    readiness=request("/intelligence/api/v1/intelligence/data-readiness")
    overview=request("/intelligence/api/v1/intelligence/research/overview")
    review=request("/api/v1/portfolio/review")
    notifications=request("/intelligence/api/v1/intelligence/notifications/summary")
    intraday=request("/api/v1/market-data/intraday-research")
    personal=request("/api/v1/research-workspace/notifications/summary")
    journal=request("/intelligence/api/v1/intelligence/journal")
    result=assess(readiness,overview,review)
    workflows=assess_workflows(readiness,overview,review,notifications)
    result["workflow_runtime"]=workflows["workflow_runtime"]
    result["investment_qualification"]=workflows["investment_qualification"]
    result["checks"].update(workflows["checks"])
    final=assess_final_contracts(intraday,personal,journal,review)
    result["checks"].update(final.pop("checks"))
    result.update(final)
    if include_advanced_audit:
        result["advanced_audit"]=advanced_audit(readiness,overview,review,intraday)
    if include_qualification_audit:
        result["qualification_audit"]=qualification_audit(overview,readiness,intraday)
    if include_recovery_audit:
        history=request("/api/v1/data-health/history-recovery")
        providers=request("/intelligence/api/v1/intelligence/data-hub/provider-adapters")
        result["recovery_audit"]=recovery_audit(history,readiness,overview,providers)
    if workflows["workflow_runtime"]!="PASS" or final["final_runtime"]!="PASS":
        result["runtime"]="BLOCKED"
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",choices=BASES,default=BASES[0])
    parser.add_argument("--require-live",action="store_true",help="Require a fresh tick during an expected live trading session")
    parser.add_argument("--qualification-audit",action="store_true",help="Include redacted stock and fund evidence gap counts")
    parser.add_argument("--advanced-audit",action="store_true",help="Audit advanced decision and validation contracts; require them to pass")
    parser.add_argument("--recovery-audit",action="store_true",help="Audit recovery diagnostics and historical display isolation; require contracts to pass")
    args=parser.parse_args()
    session=LocalSession(args.base_url)
    result=None
    try:
        email=input("Local ATLAS account email: ").strip()
        password=getpass.getpass("Local ATLAS password: ")
        try:
            login=session.request("/api/v1/auth/login","POST",{"email":email,"password":password})
        finally:
            del password
        token=login.get("access_token")
        if not isinstance(token,str) or not token:raise RuntimeError("SESSION_TOKEN_MISSING")
        session.token=token
        del login,token
        session.request("/api/v1/auth/me")
        result=collect(session.request,include_qualification_audit=args.qualification_audit,include_advanced_audit=args.advanced_audit,include_recovery_audit=args.recovery_audit)
    except (RuntimeError,ValueError,TypeError,KeyError,AttributeError):
        print(json.dumps({"runtime":"BLOCKED","reason":"LOCAL_ACCEPTANCE_REQUEST_OR_CONTRACT_FAILED"}))
        return 1
    finally:
        if session.token:
            try:session.request("/api/v1/auth/logout","POST")
            except (RuntimeError,ValueError):
                if result is not None:result["runtime"]="BLOCKED";result["checks"]["session_logout"]="BLOCKED"
            finally:session.token=None
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["runtime"]==result["stored_provider_evidence"]=="PASS" and (not args.require_live or result["live_feed"]=="OBSERVED") and (not args.advanced_audit or result["advanced_audit"]["status"]=="PASS") and (not args.recovery_audit or result["recovery_audit"]["status"]=="PASS") else 1

if __name__=="__main__":
    raise SystemExit(main())
