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

SECTIONS={"NSE","BSE","LARGE_CAP","MID_CAP","SMALL_CAP","FLEXI_CAP","INDEX"}
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
          review["opportunity_context"].get("status") in ("NO_CURRENT_WATCH_EVIDENCE","WATCH_EVIDENCE_AVAILABLE","DISABLED"))
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
    check("equity_history_eligible",any(type((rows.get(key,{}).get("result") or {}).get("eligible_count")) is int and
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

def collect(request):
    readiness=request("/intelligence/api/v1/intelligence/data-readiness")
    overview=request("/intelligence/api/v1/intelligence/research/overview")
    review=request("/api/v1/portfolio/review")
    return assess(readiness,overview,review)

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
