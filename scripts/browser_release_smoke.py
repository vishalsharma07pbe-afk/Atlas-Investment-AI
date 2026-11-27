#!/usr/bin/env python3
"""Real Chromium smoke on the disposable CI development stack only."""
import argparse
import uuid
from datetime import date, timedelta
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

PAGES=("Overview","My Portfolio","Intraday","Swing Trading","Short-Term Equity",
       "Long-Term Investments","Mutual Funds","Market Intelligence","Stock Explorer","AI Research","Settings")

def run():
    base="http://127.0.0.1:5173"
    email=f"browser-{uuid.uuid4().hex}@example.test"
    password="disposable-browser-password-123"
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":1440,"height":900},reduced_motion="reduce")
        errors=[]
        page=context.new_page()
        page.on("pageerror",lambda exc:errors.append(exc.stack or str(exc)))
        try:
            registration=context.request.post(base+"/api/v1/auth/register",data={"email":email,"password":password})
            assert registration.ok,"disposable registration failed"
            page.goto(base,wait_until="domcontentloaded")
            expect(page.get_by_role("heading",name="Welcome back")).to_be_visible(timeout=20000)
            page.get_by_label("Account email").fill(email)
            page.get_by_label("Account password").fill(password)
            page.get_by_role("button",name="Open dashboard").click()
            expect(page.get_by_role("heading",name="Overview",exact=True)).to_be_visible(timeout=20000)
            # Reopen the guide explicitly rather than racing the initial mount.
            page.get_by_role("button",name="Help",exact=True).click()
            guide=page.locator("section.onboarding")
            expect(guide).to_be_visible()
            guide.locator("button.onboarding-dismiss").click()
            expect(guide).to_have_count(0)
            assert page.evaluate("localStorage.getItem('atlas:onboarding-complete:v1')")=="true","onboarding dismissal was not persisted"
            navigation=page.locator("#atlas-workspace-nav")
            def go(title):
                button=navigation.get_by_role("button",name=title,exact=True)
                if not navigation.is_visible():
                    page.locator(".workspace-menu-toggle").click()
                expect(button).to_be_visible()
                button.click()
                expect(page.get_by_role("heading",name=title,exact=True,level=1)).to_be_visible()
            Path("browser-preview").mkdir(exist_ok=True)
            for title in PAGES:
                go(title)
                expect(navigation.get_by_role("button",name=title,exact=True)).to_have_attribute("aria-current","page")
                page.screenshot(path="browser-preview/desktop-"+title.lower().replace(" ","-")+".png",timeout=5000)
            page.set_viewport_size({"width":375,"height":900})
            for title in PAGES:
                go(title)
                expect(page.locator("main.content")).to_be_visible()
                assert page.locator("main.content").evaluate("(el)=>{const r=el.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1}"),f"workspace overflows viewport: {title}"
                if title in ("Overview","Mutual Funds","Swing Trading","AI Research","Settings"):
                    page.screenshot(path="browser-preview/mobile-"+title.lower().replace(" ","-")+".png",timeout=5000)
            page.set_viewport_size({"width":1440,"height":900})
            go("Overview")
            expect(page.get_by_role("region",name="Portfolio attention summary")).to_be_visible()
            expect(page.get_by_role("region",name="Automatic research overview")).to_be_visible()
            expect(page.get_by_role("region",name="Recorded portfolio charts")).to_be_visible()
            expect(page.get_by_text("No recorded valuations",exact=True)).to_be_visible()
            assert page.locator(".dashboard").evaluate("(el)=>getComputedStyle(el).getPropertyValue('--terminal-surface').trim().length > 0"),"terminal stylesheet not applied"
            Path("browser-preview").mkdir(exist_ok=True)
            page.screenshot(path="browser-preview/overview-desktop.png",timeout=5000)
            # Verify both saved theme variants on the actual application.
            for theme in ("dark","light"):
                page.get_by_role("button",name="Open appearance settings").click()
                panel=page.get_by_role("dialog",name="Appearance settings")
                expect(panel).to_be_visible()
                assert panel.evaluate("(el)=>{const r=el.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1 && r.top>=-1 && r.bottom<=innerHeight+1}"),"appearance drawer outside viewport"
                panel.get_by_role("group",name="Theme").get_by_role("button",name=re.compile(theme,re.I)).click()
                expect(page.locator(".dashboard")).to_have_attribute("data-theme",theme)
                # Appearance is a live preview, not a page-scroll lock.
                for opacity,blur in ((0,0),(65,20),(100,40)):
                    panel.locator("#panel-opacity").fill(str(opacity))
                    panel.locator("#panel-blur").fill(str(blur))
                    assert page.evaluate("getComputedStyle(document.documentElement).overflowY !== 'hidden' && getComputedStyle(document.body).overflowY !== 'hidden'"),"appearance must not lock page scrolling"
                    page.evaluate("window.scrollTo(0,0)")
                    page.mouse.move(500,780)
                    page.mouse.wheel(0,350)
                    # Main document may be shorter than the viewport on empty fixtures.
                    if page.evaluate("document.scrollingElement.scrollHeight > innerHeight + 20"):
                        page.wait_for_function("window.scrollY > 0")
                panel.locator("#panel-opacity").fill("72")
                panel.locator("#panel-blur").fill("20")
                page.keyboard.press("Escape")
                page.screenshot(path=f"browser-preview/overview-{theme}.png",timeout=5000)
            # Verify navigation and overlay controls on narrow and desktop layouts.
            for width in (768,320,1440):
                page.set_viewport_size({"width":width,"height":900})
                go("My Portfolio")
                expect(page.get_by_role("region",name="Recorded portfolio charts")).to_be_visible()
                expect(page.get_by_role("region",name="Recorded valuation history")).to_be_visible()
                assert page.locator(".terminal-portfolio-visuals").evaluate("(el)=>{const r=el.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1}"),f"portfolio charts overflow viewport {width}"
                if width in (320,1440):
                    page.screenshot(path=f"browser-preview/portfolio-{width}.png",timeout=5000)
                page.get_by_role("button",name="Open appearance settings").click()
                panel=page.get_by_role("dialog",name="Appearance settings")
                expect(panel).to_be_visible()
                assert panel.evaluate("(el)=>{const r=el.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1 && r.top>=-1 && r.bottom<=innerHeight+1}"),f"appearance drawer outside viewport {width}"
                panel.get_by_role("group",name="Theme").get_by_role("button",name=re.compile("dark",re.I)).click()
                expect(page.locator(".dashboard")).to_have_attribute("data-theme","dark")
                page.keyboard.press("Escape")
                expect(page.get_by_role("dialog",name="Appearance settings")).to_have_count(0)
            # Exercise the actual chart library in Chromium using a synthetic fixture
            # intercepted only in this disposable browser context, never in the app.
            go("Stock Explorer")
            instrument={"id":987654,"exchange":"NSE","symbol":"UIFIXTURE","series":"EQ",
                        "isin":"INE000000001","security_name":"Synthetic CI chart fixture",
                        "listing_status":"ACTIVE","source":"CI_FIXTURE","source_revision":None}
            candles=[]
            for i in range(80):
                day=(date(2026,1,1)+timedelta(days=i)).isoformat()
                close=100+i*0.6+(i%5-2)*2
                candles.append({"trade_date":day,"open":close-1,"high":close+2,"low":close-3,
                    "close":close,"volume":1000+i*15,"adjustment_status":"RAW_UNADJUSTED",
                    "source_code":"CI_FIXTURE","received_at":day+"T18:00:00Z"})
            search_pattern=re.compile(r"/api/v1/instruments\?")
            page.route(search_pattern,lambda route:route.fulfill(json=[instrument]))
            page.route("**/intelligence/api/v1/intelligence/technical/987654",lambda route:route.fulfill(json={
                "instrument":instrument,"status":"AVAILABLE","as_of":candles[-1]["trade_date"],
                "candle_count":len(candles),"candles":candles,"indicators":{},"patterns":[]}))
            page.route("**/intelligence/api/v1/intelligence/technical/987654/summary",
                       lambda route:route.fulfill(json={"research":None,"notice":"CI fixture only"}))
            page.route(re.compile(r"/providers/upstox/resolve\?instrument_id=987654"),
                       lambda route:route.fulfill(json={"subscription_ready":False,"blocker":"CI_FIXTURE"}))
            page.get_by_role("textbox",name="Instrument search").fill("UIFIXTURE")
            page.get_by_role("button",name=re.compile("NSE:UIFIXTURE")).click()
            chart=page.get_by_role("region",name="Stock price and volume chart")
            expect(chart.locator("canvas").first).to_be_visible(timeout=10000)
            expect(chart.get_by_text("Chart rendering is unavailable.",exact=False)).to_have_count(0)
            page.get_by_role("button",name="1M",exact=True).click()
            page.get_by_role("button",name="Line",exact=True).click()
            expect(chart.locator("canvas").first).to_be_visible()
            expect(chart.get_by_text("Chart rendering is unavailable.",exact=False)).to_have_count(0)
            page.get_by_role("button",name="Candles",exact=True).click()
            chart.scroll_into_view_if_needed()
            page.screenshot(path="browser-preview/stock-chart-CI-fixture-desktop.png",timeout=5000)
            page.set_viewport_size({"width":375,"height":900})
            assert chart.evaluate("(el)=>{const r=el.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1}"),"stock chart overflows mobile viewport"
            chart.scroll_into_view_if_needed()
            page.screenshot(path="browser-preview/stock-chart-CI-fixture-mobile.png",timeout=5000)
            page.set_viewport_size({"width":1440,"height":900})
            page.unroute_all(behavior="wait")
            go("My Portfolio")
            page.reload(wait_until="domcontentloaded")
            expect(page.get_by_role("heading",name="My Portfolio",exact=True,level=1)).to_be_visible(timeout=20000)
            page.get_by_role("button",name="Logout",exact=True).click()
            expect(page.get_by_role("heading",name="Welcome back")).to_be_visible(timeout=20000)
            assert not errors,"Unhandled browser errors: "+"; ".join(errors[:5])
        except Exception:
            # Only disposable CI accounts are used here. Never capture real holdings.
            Path("browser-failure").mkdir(exist_ok=True)
            page.screenshot(path="browser-failure/page.png",full_page=True,timeout=5000)
            print("Browser failure location:",page.url)
            print("Browser errors:",errors[:5])
            raise
        context.close()
        browser.close()
    print("PASS: Chromium sign-in, 11 preserved pages, responsive navigation, appearance overlay, persistence, logout")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    parser.parse_args()
    run()
