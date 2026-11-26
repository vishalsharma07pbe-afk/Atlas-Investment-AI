#!/usr/bin/env python3
"""Production image gateway smoke with disposable CI identities, over loopback."""
import argparse
import os
import time
import uuid
from stack_contract_smoke import Browser, check
from local_research_acceptance import collect, SECTIONS

SECURITY_HEADERS={
    "X-Content-Type-Options":"nosniff",
    "X-Frame-Options":"DENY",
    "Referrer-Policy":"strict-origin-when-cross-origin",
    "Permissions-Policy":"camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy":"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}

def run():
    if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("COMPOSE_PROJECT_NAME")!="atlas-ci-production":
        raise RuntimeError("DISPOSABLE_CI_ONLY")
    service_token=os.environ.get("INTERNAL_SERVICE_TOKEN","")
    if len(service_token)<32:
        raise RuntimeError("DISPOSABLE_SERVICE_TOKEN_REQUIRED")
    gateway=Browser("http://127.0.0.1:8088")
    gateway.request("/",required_headers=SECURITY_HEADERS,expect_json=False)
    gateway.request("/healthz",required_headers=SECURITY_HEADERS)
    gateway.request("/api/v1/health")
    gateway.request("/api/v1/portfolio/review",expected=401)
    gateway.request("/intelligence/health",expected=401,required_headers=SECURITY_HEADERS)
    gateway.request("/intelligence/api/v1/intelligence/notifications/summary",expected=401)
    gateway.request("/api/v1/research-workspace/notifications/summary",expected=401)
    journal="/intelligence/api/v1/intelligence/journal"
    gateway.request(journal,expected=401)
    credentials={"email":f"production-{uuid.uuid4().hex}@example.test","password":"disposable-production-ci-password"}
    gateway.request("/api/v1/auth/register","POST",credentials)
    login=gateway.request("/api/v1/auth/login","POST",credentials)
    headers={"Authorization":"Bearer "+login["access_token"]}
    check(gateway.request("/api/v1/auth/me",headers=headers)["email"]==credentials["email"],"production session failed")
    gateway.request("/intelligence/health",headers=headers,required_headers=SECURITY_HEADERS)
    gateway.request("/intelligence/api/v1/internal/portfolio-opportunities",expected=401,headers=headers)
    # Even a valid disposable service token must not traverse the browser proxy.
    # The Spring-to-Python direct service path remains independently tested.
    gateway.request("/intelligence/api/v1/internal/portfolio-opportunities",expected=401,
        headers={**headers,"X-Atlas-Service-Token":service_token})
    gateway.request("/intelligence/api/v1/ai/providers/health",expected=401,
        headers={**headers,"X-Atlas-Service-Token":service_token})
    del service_token
    # Production cookies are Secure; urllib will not send them over this
    # disposable HTTP loopback gateway. Authenticate both test accounts with
    # their independent bearer tokens, without relaxing production settings.
    other=Browser("http://127.0.0.1:8088")
    other_credentials={"email":f"journal-{uuid.uuid4().hex}@example.test","password":"disposable-production-ci-password"}
    other.request("/api/v1/auth/register","POST",other_credentials)
    other_login=other.request("/api/v1/auth/login","POST",other_credentials)
    other_headers={"Authorization":"Bearer "+other_login["access_token"]}
    check(other.request("/api/v1/auth/me",headers=other_headers)["email"]==other_credentials["email"],"second production session failed")
    note={"symbol":"CI_NOTE","thesis":"Disposable owner-specific research note"}
    gateway.request(journal,"POST",note,expected=201,headers=headers)
    entries=gateway.request(journal,headers=headers)["entries"]
    check(len(entries)==1 and entries[0]["symbol"]=="CI_NOTE","owner research journal write failed")
    entry_id=entries[0]["id"]
    check(other.request(journal,headers=other_headers)["entries"]==[],"research journal isolation failed")
    other.request(journal+"/"+entry_id,"PUT",note,expected=404,headers=other_headers)
    other.request(journal+"/"+entry_id,"DELETE",expected=404,headers=other_headers)
    # Explicitly replay the disposable cookie to exercise the cookie-only
    # server path over HTTP. This is not a browser TLS transport test.
    other_cookie={"Cookie":"ATLAS_SESSION="+other_login["access_token"]}
    check(other.request(journal,headers=other_cookie)["entries"]==[],"cookie-authenticated journal isolation failed")
    other.request(journal+"/"+entry_id,"PUT",note,expected=404,headers=other_cookie)
    other.request(journal,"POST",note,expected=403,
        headers={**other_cookie,"Origin":"https://example.invalid","Sec-Fetch-Site":"cross-site"})
    gateway.request(journal+"/"+entry_id,"DELETE",expected=204,headers=headers)
    other.request("/api/v1/auth/logout","POST",headers=other_headers)
    other.request(journal,expected=401,headers=other_headers)
    other.request(journal,expected=401,headers=other_cookie)
    del other_login,other_headers,other_cookie
    personal=gateway.request("/api/v1/research-workspace/notifications/summary",headers=headers)
    check(type(personal.get("unread_count")) is int and personal["unread_count"]>=0,"personal notification summary contract failed")
    gateway.request("/api/v1/portfolio/holdings","POST",
        {"symbol":"CI_PROD","assetType":"EQUITY","quantity":2,"averageCost":100,"lastPrice":80},headers=headers)
    review=gateway.request("/api/v1/portfolio/review",headers=headers)
    check(review["holding_count"]==1 and review["holdings"][0]["symbol"]=="CI_PROD","production portfolio review failed")
    check(review["opportunity_context"]["status"]!="UNAVAILABLE","production internal intelligence unavailable")
    deadline=time.monotonic()+120
    while True:
        snapshot=gateway.request("/intelligence/api/v1/intelligence/research/overview",headers=headers)
        if SECTIONS<={s["section"] for s in snapshot["sections"] if s["status"]=="READY"}:
            break
        check(time.monotonic()<deadline,"production automatic research never reached READY")
        time.sleep(3)
    acceptance=collect(lambda path: gateway.request(path,headers=headers))
    check(acceptance["runtime"]=="PASS","local acceptance runtime contract blocked")
    check(acceptance["workflow_runtime"]=="PASS","current research workflow contract blocked")
    check(acceptance["investment_qualification"]=="NOT_CERTIFIED","synthetic evidence incorrectly certified investments")
    check(acceptance["stored_provider_evidence"]=="BLOCKED","empty CI provider data incorrectly accepted")
    check(acceptance["live_feed"]=="NOT_OBSERVED","unauthorized CI feed incorrectly accepted")
    gateway.request("/api/v1/auth/logout","POST",headers=headers)
    gateway.request("/api/v1/auth/me",expected=401,headers=headers)
    gateway.request("/intelligence/health",expected=401,headers=headers)
    gateway.request("/intelligence/api/v1/intelligence/notifications/summary",expected=401,headers=headers)
    gateway.request("/api/v1/research-workspace/notifications/summary",expected=401,headers=headers)
    gateway.request(journal,expected=401,headers=headers)
    print("PASS: production gateway, authorization, portfolio review, internal research, logout")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    parser.parse_args()
    run()
