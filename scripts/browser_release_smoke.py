#!/usr/bin/env python3
"""Real Chromium smoke on the disposable CI development stack only."""
import argparse
import uuid
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
        page.on("pageerror",lambda exc:errors.append(str(exc)))
        registration=context.request.post(base+"/api/v1/auth/register",data={"email":email,"password":password})
        assert registration.ok,"disposable registration failed"
        page.goto(base,wait_until="domcontentloaded")
        expect(page.get_by_role("heading",name="Welcome back")).to_be_visible(timeout=20000)
        page.get_by_label("Account email").fill(email)
        page.get_by_label("Account password").fill(password)
        page.get_by_role("button",name="Open dashboard").click()
        expect(page.get_by_role("heading",name="Overview",exact=True)).to_be_visible(timeout=20000)
        dismiss=page.get_by_role("button",name="Dismiss",exact=True)
        if dismiss.is_visible():dismiss.click()
        navigation=page.locator("#atlas-workspace-nav")
        for title in PAGES:
            navigation.get_by_role("button",name=title,exact=True).click()
            expect(page.get_by_role("heading",name=title,exact=True,level=1)).to_be_visible()
            expect(navigation.get_by_role("button",name=title,exact=True)).to_have_attribute("aria-current","page")
        navigation.get_by_role("button",name="Overview",exact=True).click()
        expect(page.get_by_role("region",name="Portfolio attention summary")).to_be_visible()
        expect(page.get_by_role("region",name="Automatic research overview")).to_be_visible()
        # Verify navigation and overlay controls on narrow and desktop layouts.
        for width in (768,320,1440):
            page.set_viewport_size({"width":width,"height":900})
            toggle=page.locator(".workspace-menu-toggle")
            if toggle.is_visible():
                toggle.click()
            navigation.get_by_role("button",name="My Portfolio",exact=True).click()
            expect(page.get_by_role("heading",name="My Portfolio",exact=True,level=1)).to_be_visible()
            page.get_by_role("button",name="Open appearance settings").click()
            expect(page.get_by_role("dialog",name="Appearance settings")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.get_by_role("dialog",name="Appearance settings")).to_have_count(0)
        page.reload(wait_until="domcontentloaded")
        expect(page.get_by_role("heading",name="My Portfolio",exact=True,level=1)).to_be_visible(timeout=20000)
        page.get_by_role("button",name="Logout",exact=True).click()
        expect(page.get_by_role("heading",name="Welcome back")).to_be_visible(timeout=20000)
        assert not errors,"Unhandled browser errors: "+"; ".join(errors[:5])
        context.close()
        browser.close()
    print("PASS: Chromium sign-in, 11 preserved pages, responsive navigation, appearance overlay, persistence, logout")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disposable-ci-stack",action="store_true",required=True)
    parser.parse_args()
    run()
