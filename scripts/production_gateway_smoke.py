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
    print("PASS: production gateway, authorization, portfolio review, internal research, logout")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    parser.parse_args()
    run()
