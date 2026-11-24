#!/usr/bin/env python3
"""Disposable local CI stack contract checks. Never run against personal data."""
import argparse
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid

def check(condition, label):
    if not condition:
        raise AssertionError(label)

class Browser:
    def __init__(self, base):
        self.base=base
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self,path,method="GET",body=None,expected=200,headers=None):
        request_headers={"Accept":"application/json","Origin":self.base,"Sec-Fetch-Site":"same-origin"}
        if body is not None:
            request_headers["Content-Type"]="application/json"
        request_headers.update(headers or {})
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
                                   method=method,headers=request_headers)
        try:
            with self.opener.open(req,timeout=15) as response:
                code=response.status
                raw=response.read(2_000_001)
        except urllib.error.HTTPError as error:
            code=error.code
            raw=b""
        check(code==expected,f"{method} {path}: expected {expected}, got {code}")
        check(len(raw)<=2_000_000,"response exceeds smoke limit")
        return json.loads(raw) if raw and expected==200 else None

def run(base):
    anonymous=Browser(base)
    anonymous.request("/api/v1/portfolio/review",expected=401)
    anonymous.request("/intelligence/api/v1/internal/portfolio-opportunities",expected=401)
    users=[Browser(base),Browser(base)]
    tokens=[]
    for browser in users:
        credentials={"email":f"smoke-{uuid.uuid4().hex}@example.test","password":"disposable-smoke-password-123"}
        browser.request("/api/v1/auth/register","POST",credentials)
        login=browser.request("/api/v1/auth/login","POST",credentials)
        tokens.append(login["access_token"])
        check(browser.request("/api/v1/auth/me")["email"]==credentials["email"],"session cookie did not authenticate")
    a,b=users
    a.request("/api/v1/portfolio/holdings","POST",
              {"symbol":"SMOKE_A","assetType":"EQUITY","quantity":2,"averageCost":100,"lastPrice":80})
    b.request("/api/v1/portfolio/holdings","POST",
              {"symbol":"SMOKE_B","assetType":"EQUITY","quantity":1,"averageCost":100,"lastPrice":120})
    for browser,symbol in zip(users,("SMOKE_A","SMOKE_B")):
        holdings=browser.request("/api/v1/portfolio/holdings")
        check(len(holdings)==1 and holdings[0]["symbol"]==symbol,"holding isolation failed")
        review=browser.request("/api/v1/portfolio/review")
        check(review["holding_count"]==1 and review["holdings"][0]["symbol"]==symbol,"review isolation failed")
        check("thesis_summary" in review["holdings"][0],"thesis digest missing")
        check("diversification" in review,"diversification missing")
        check(review["opportunity_context"]["status"]!="UNAVAILABLE","Spring-to-Python opportunity read failed")
    # The autonomous scheduler must complete real internal HTTP registry reads,
    # even on the intentionally empty test database.
    deadline=time.monotonic()+90
    while True:
        snapshot=a.request("/intelligence/api/v1/intelligence/research/overview")
        ready={s["section"] for s in snapshot["sections"] if s["status"]=="READY"}
        if {"NSE","BSE"}<=ready:
            break
        check(time.monotonic()<deadline,"automatic market research never reached READY")
        time.sleep(3)
    check(snapshot["enabled"] is True,"autonomous research not enabled")
    check("research_reliability" in snapshot and "strategy_validation" in snapshot,"automatic research diagnostics missing")
    a.request("/api/v1/auth/logout","POST")
    a.request("/api/v1/auth/me",expected=401)
    anonymous.request("/api/v1/auth/me",expected=401,headers={"Authorization":"Bearer "+tokens[0]})
    b.request("/api/v1/auth/me")
    print("PASS: cookie writes, owner isolation, private portfolio research, real public scheduler HTTP, logout")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:5173",choices=["http://127.0.0.1:5173"])
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    run(parser.parse_args().base_url)
