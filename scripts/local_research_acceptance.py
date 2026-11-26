#!/usr/bin/env python3
"""Read-only acceptance of the running ATLAS research application.

Only loopback HTTP, no redirects, no environment proxies, no response dumps.
The interactive password and short-lived use of a session token stay in memory.
No registration, holdings mutation, forced refresh, provider call or trade.
"""
import argparse
import getpass
import json
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
    entries=journal.get("entries")
    journal_ok=isinstance(entries,list) and len(entries)<=200 and all(
        isinstance(e,dict) and isinstance(e.get("id"),str) and bool(e["id"])
        and e.get("status") in ("IDEA","RESEARCHING","MONITORING","CLOSED") for e in entries)
    if journal_ok:
        journal_ok=len({e["id"] for e in entries})==len(entries)
    checks={
        "intraday_watch_contract":"PASS" if intraday_ok else "BLOCKED",
        "private_notification_summary":"PASS" if _count(personal.get("unread_count")) else "BLOCKED",
        "private_research_journal_contract":"PASS" if journal_ok else "BLOCKED",
    }
    populated=_count(review.get("holding_count")) and review["holding_count"]>0 and isinstance(review.get("holdings"),list) and len(review["holdings"])==review["holding_count"]
    return {"checks":checks,"final_runtime":"PASS" if all(v=="PASS" for v in checks.values()) else "BLOCKED",
        "populated_portfolio":"OBSERVED" if populated else "NOT_OBSERVED",
        "intraday_evidence":"OBSERVED" if intraday_ok and status=="RESEARCH_ONLY" and eligible>0 else "NOT_OBSERVED",
        "product_acceptance":"NOT_CERTIFIED",
        "remaining_acceptance":["AUTHORIZED_SOURCE_COVERAGE","QUALIFIED_INVESTMENT_RESEARCH",
            "POPULATED_PORTFOLIO_ACCURACY","ACTUAL_LOCAL_UPGRADE_AND_RECOVERY",
            "REPRESENTATIVE_RESOURCE_AND_UX_VERIFICATION","ACTUAL_LOCAL_PRIVACY_VERIFICATION"]}

def collect(request):
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
    if workflows["workflow_runtime"]!="PASS" or final["final_runtime"]!="PASS":
        result["runtime"]="BLOCKED"
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",choices=BASES,default=BASES[0])
    parser.add_argument("--require-live",action="store_true",help="Require a fresh tick during an expected live trading session")
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
        result=collect(session.request)
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
    return 0 if result["runtime"]==result["stored_provider_evidence"]=="PASS" and (not args.require_live or result["live_feed"]=="OBSERVED") else 1

if __name__=="__main__":
    raise SystemExit(main())
