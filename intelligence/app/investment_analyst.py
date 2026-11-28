"""Decision-oriented projection of existing current public research.

This layer prioritizes an investigation, not a trade. Certification, replay,
alerts and external exports continue to consume their existing strict contracts.
No private holdings, new network requests, model calls, or stored data changes.
"""
from collections import Counter
from datetime import date
from math import isfinite
import re
from . import company_reports, company_venues, steady_momentum, fip_research, forward_earnings, quarterly_financials
from .replay_evidence import exact_isin
from . import research_synthesis

VERSION="INVESTMENT-ANALYST-1"
CORE_FUNDS=("LARGE_CAP","MID_CAP","SMALL_CAP")
NOTICE="Conditional research recommendations, not certified buy/sell instructions or predicted returns. Missing evidence lowers the scope of the conclusion, not the truth of the observations."
def obj(v):return v if isinstance(v,dict) else {}
def rows(v):return v if isinstance(v,list) else []
def num(v,lo,hi):return type(v) in (float,int) and isfinite(v) and lo<=v<=hi
def fresh(v,today,limit,minimum=0):
    try:return minimum<=(today-date.fromisoformat(v)).days<=limit
    except (ValueError,TypeError):return False
def named(v):return isinstance(v,str) and 0<len(v)<=300
def flagged(row):
    return (row.get("security_state") in company_venues.SPECIAL
        or bool(obj(row.get("governance_review")).get("findings"))
        or bool(obj(row.get("company_venue_context")).get("review_findings"))
        or bool(obj(row.get("stock_qualification")).get("review_findings"))
        or bool(obj(row.get("elite_assessment")).get("review_findings"))
        or obj(obj(obj(row.get("ai_review")).get("committee")).get("claim_comparison")).get("status")
           in ("CONFLICTING_ASSERTIONS","CONTRADICTED_ASSERTIONS_PRESENT"))
def price_plan(row,horizon):
    # An explicit risk-budget scenario, not a forecast or execution price.
    close=row.get("close");atr=row.get("atr_percent")
    if horizon not in ("ELITE","SWING") or row.get("adjustment_status")!="ADJUSTED" or not num(close,.01,1e8) or not num(atr,.01,5):return None
    risk=close*2*atr/100
    entry,stop,target=round(close,2),round(close-risk,2),round(close+2*risk,2)
    if not 0<stop<entry<target:return None
    return {"reference":entry,"stop_scenario":stop,"target_scenario":target,
        "reward_risk":round((target-entry)/(entry-stop),2),"method":"TWO_ATR_RISK_TWO_R_SCENARIO",
        "notice":"Illustrative prior-close scenario, not a price forecast. Recheck live quote, spread, costs and gap risk before any order."}

def stock_growth(row,instant):
    if instant is None:return None
    company=obj(row.get("company_evidence"))
    if company.get("isin")!=row.get("isin"):return None
    baseline=forward_earnings.baseline(company,instant)
    return baseline_growth(baseline)

def baseline_growth(baseline):
    if not baseline:return None
    return {"status":"UNCALIBRATED_EARNINGS_SCENARIO","observed_quarter":baseline["observed_quarter"],
        "target_quarter":baseline["target_quarter"],
        "revenue_yoy_percent":baseline["metrics"]["revenue"]["persisted_growth_percent"],
        "profit_yoy_percent":baseline["metrics"]["net_profit"]["persisted_growth_percent"],
        "amount_scenarios":research_synthesis.quarter_scenarios(baseline),
        "notice":"Quarterly persistence scenario, not consensus earnings or stock return forecast."}

def fund_growth(driver,today):
    e=obj(driver.get("experimental_forward"))
    try:
        observed=date.fromisoformat(e["observed_quarter"]);target=date.fromisoformat(e["target_quarter"])
        if (e.get("status")!="UNCALIBRATED_PERSISTENCE_EXPERIMENT" or e.get("qualified") is not False
            or e["observed_quarter"]!=driver.get("quarter") or quarterly_financials.shift(observed,3)!=target
            or not observed<today<target or not num(e.get("covered_weight_percent"),70,100.5)
            or not num(e.get("positive_joint_growth_weight_percent"),0,e["covered_weight_percent"])
            or not num(e.get("covered_subset_revenue_persistence_percent"),-50,100)
            or not num(e.get("covered_subset_profit_persistence_percent"),-50,100)):return None
        return {"status":"UNCALIBRATED_UNDERLYING_GROWTH_SCENARIO","observed_quarter":e["observed_quarter"],
            "target_quarter":e["target_quarter"],"coverage_percent":e["covered_weight_percent"],
            "revenue_yoy_percent":e["covered_subset_revenue_persistence_percent"],
            "profit_yoy_percent":e["covered_subset_profit_persistence_percent"],
            "driver_scenarios":[{"case":case,"revenue_yoy_percent":round(e["covered_subset_revenue_persistence_percent"]+shift,4),"profit_yoy_percent":round(e["covered_subset_profit_persistence_percent"]+shift,4)} for case,shift in (("BEAR",-10),("BASE",0),("BULL",10))],
            "notice":"Persistence scenario for covered original fund weight only; not a fund NAV forecast."}
    except (ValueError,TypeError,KeyError):return None

def stock_projection(snapshot,instant=None):
    screen=obj(snapshot.get("steady_momentum"))
    strict=obj(screen.get("strict_suggestions"));reported=obj(screen.get("reported_suggestions"))
    # Match the actual objects accepted by the current-session company read model.
    entries=list(company_reports.entries(snapshot))
    prohibited={r["isin"] for _,r in entries if flagged(r)}
    elite_ids={id(r) for h,r in entries if h=="ELITE"}
    seen=set();out=[]
    def add(r,tier,horizon,score,reasons,gaps):
        if (not isinstance(r,dict) or r.get("isin") in prohibited or r.get("isin") in seen
            or not exact_isin(r.get("isin")) or not isinstance(r.get("symbol"),str)
            or not re.fullmatch(r"[A-Z0-9._&-]{1,50}",r["symbol"])
            or not num(r.get("close"),.0001,1e8)):return
        seen.add(r["isin"])
        facts={k:r[k] for k,lo,hi in (("earnings_growth_percent",10,100),("eps_growth_percent",10,100),
            ("sales_growth_percent",5,10000),("reported_pe",.0001,40),("reported_sector_pe",.0001,1e6),
            ("median_daily_turnover_cr",5,1e10),("atr_percent",.01,5),("return_60_percent",-100,100))
            if num(r.get(k),lo,hi)}
        growth=stock_growth(r,instant)
        risk=obj(obj(r.get("elite_assessment")).get("historical_risk")).get("historical_price_risk")
        if risk not in ("LOW","MEDIUM","HIGH"):
            atr=r.get("atr_percent")
            risk=("HIGH" if atr>=4 else "MEDIUM" if atr>=2 else "LOW") if num(atr,.01,5) else None
        out.append({k:r[k] for k in ("id","isin","symbol","exchange","as_of","close")}|
            {"tier":tier,"horizon":horizon,"score":score,"reasons":reasons,"limitations":gaps,
             "qualified":False,"price_plan":price_plan(r,horizon),
             "risk":risk,"risk_basis":"HISTORICAL_PRICE_RISK_PROXY","growth_outlook":growth,"observed_facts":facts,
             "cash_sensitivity":research_synthesis.cash_context(obj(r.get("company_evidence")).get("valuation_sensitivity")),
             "evidence_confidence":"MODERATE" if tier=="ADJUSTED_JOINT" and growth else "LIMITED" if tier in ("ADJUSTED_JOINT","REPORTED_JOINT","BUSINESS_SCREEN") else "LOW",
             "action":"RESEARCH_FOR_ENTRY" if tier=="ADJUSTED_JOINT" else "WATCH_FOR_CONFIRMATION"})
    for report,status,tier,key,basis in ((strict,"JOINT_SCREEN_MATCHES","ADJUSTED_JOINT","strict_fip_evidence","ADJUSTED"),
            (reported,"REPORTED_JOINT_MATCHES","REPORTED_JOINT","reported_fip_evidence","RAW_UNADJUSTED")):
        if report.get("status")!=status or report.get("qualification_eligible") is not False:continue
        for r in rows(report.get("items"))[:10]:
            if id(r) not in elite_ids:continue
            e=obj(r.get(key))
            if (e.get("as_of")!=r.get("as_of") or e.get("adjustment_status")!=basis or e.get("calendar_status")!="STORED_SESSIONS_MATCHED"
                or not num(e.get("score"),0,100) or not num(obj(obj(e.get("windows")).get("252")).get("return_percent"),.00001,99.99999)):continue
            if tier=="ADJUSTED_JOINT":
                if not steady_momentum.strict_fip_match(r):continue
            elif (e.get("status")!="REPORTED_PRICE_MATCH" or e.get("methodology")!=fip_research.REPORTED_VERSION
                or e.get("adjustment_verified") is not False or e.get("qualification_eligible") is not False):continue
            if (r.get("adjustment_status")!=basis or not num(r.get("earnings_growth_percent"),10,100)
                or not num(r.get("eps_growth_percent"),10,100) or not num(r.get("reported_pe"),.0001,40)
                or not num(r.get("median_daily_turnover_cr"),5,1e10)):continue
            reasons=["Steady four-window momentum screen passed.",
                f"Reported annual profit growth {r['earnings_growth_percent']:.1f}%; EPS growth {r['eps_growth_percent']:.1f}%.",
                f"Reported P/E {r['reported_pe']:.1f}; median daily turnover ₹{r['median_daily_turnover_cr']:.1f} crore."]
            gaps=["Independent filing/valuation and prospective performance not certified."]
            if basis!="ADJUSTED":gaps.append("Historical adjustment basis unverified; no price plan.")
            add(r,tier,"ELITE",e["score"],reasons,gaps)
    # Use already-consolidated business screens only when joint FIP is absent.
    # Never describe a business-only match as having passed FIP.
    if not out:
        for r in rows(screen.get("items"))[:10]:
            if id(r) not in elite_ids or r.get("technical_rating")!="ATLAS_STRONG_BULLISH":continue
            a=obj(r.get("elite_assessment"));score=a.get("score")
            if a.get("status")!="PRELIMINARY_SCORE_ONLY" or not num(score,0,100):continue
            w=obj(obj(r.get("momentum_windows")).get("252"))
            if not num(w.get("return_percent"),0,99.99999) or w.get("last_date")!=r.get("as_of"):continue
            if not num(r.get("earnings_growth_percent"),10,100) or not num(r.get("reported_pe"),.0001,40):continue
            add(r,"BUSINESS_SCREEN","ELITE",score,["Bullish technical and reported business screen passed.",
                f"Reported profit growth {r['earnings_growth_percent']:.1f}%; reported P/E {r['reported_pe']:.1f}."],
                ["Joint Frog in the Pan qualification not established.","Reported valuation and price adjustment may be unverified."])
    # Independent strategy lanes can surface non-FIP opportunities. Reserve up
    # to three discovery slots without changing strict FIP exports/qualification.
    alternatives=obj(snapshot.get("multi_strategy"))
    if alternatives.get("methodology")=="MULTI-STRATEGY-1":
        # Do not promote a cached candidate from an older completed session.
        current_sessions=set()
        for section in rows(snapshot.get("sections")):
            if not isinstance(section,dict) or section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):continue
            coverage=obj(obj(section.get("result")).get("discovery_coverage"))
            if (coverage.get("calendar_checked_on")==snapshot.get("research_date") and coverage.get("calendar_status")=="PUBLISHED_SESSION"
                and isinstance(coverage.get("expected_session"),str)):
                current_sessions.add((section["section"],coverage["expected_session"]))
        alt=[r for r in rows(alternatives.get("items")) if isinstance(r,dict) and r.get("qualified") is False and exact_isin(r.get("isin")) and r["isin"] not in prohibited and r["isin"] not in seen and num(r.get("close"),.0001,1e9)
             and (r.get("exchange"),r.get("as_of")) in current_sessions]
        if alt:
            out=out[:max(7,10-min(3,len(alt)))]
            for r in alt:
                if len(out)>=10:break
                if r["isin"] in seen:continue
                seen.add(r["isin"])
                plan=obj(r.get("price_plan"))
                if (r.get("adjustment_verified_for_screen") is not True or plan.get("qualified") is not False
                    or plan.get("method")!="STRATEGY_RISK_GEOMETRY_V1" or plan.get("strategy") not in r["strategies"]
                    or not all(num(plan.get(k),.01,1e9) for k in ("reference","stop_scenario","target_scenario"))
                    or not num(plan.get("reward_risk"),0,1e9) or not named(plan.get("notice"))
                    or not plan["stop_scenario"]<plan["reference"]<plan["target_scenario"]
                    or abs(plan["reference"]-r["close"])>.0051):plan=None
                baseline=obj(r.get("earnings_baseline"))
                growth=baseline_growth(baseline) if research_synthesis.current_baseline(baseline,r["isin"],instant) else None
                out.append({**{k:r[k] for k in ("id","isin","symbol","exchange","as_of","close")},
                    "tier":"MULTI_STRATEGY_RESEARCH","horizon":"RESEARCH","score":None,"qualified":False,"action":"WATCH_FOR_CONFIRMATION",
                    "risk":None,"growth_outlook":growth,"price_plan":plan,"evidence_confidence":"LIMITED",
                    "strategy_diagnostics":obj(r.get("strategy_diagnostics")),
                    "cash_sensitivity":research_synthesis.cash_context(r.get("cash_sensitivity")),
                    "strategies":r["strategies"],"strategy_families":r["families"],"observed_facts":r["observed_facts"],
                    "reasons":["Independent strategy research matches: "+", ".join(x.replace("_"," ").lower() for x in r["strategies"])],
                    "limitations":["Fixed research proxies; independent strategy performance not established.","No allocation or execution qualification; price adjustment and valuation evidence may be incomplete."]})
    # A separate technical-only fallback is a lead to investigate, not a buy.
    # Horizon rank scores are deliberately not compared across horizons.
    if not out:
        for horizon in ("SWING","SHORT_TERM","LONG_TERM"):
            for h,r in entries:
                if h!=horizon or r.get("adjustment_status") not in ("ADJUSTED","RAW_UNADJUSTED"):continue
                reasons=[v for v in rows(r.get("reasons"))[:3] if named(v)]
                if not reasons:continue
                add(r,"TECHNICAL_LEAD",horizon,None,reasons,["Business and valuation thesis not established.",
                    "Technical observation only; not a Frog in the Pan match."])
                if len(out)>=10:break
            if len(out)>=10:break
    return out[:10]

def fund_projection(snapshot,today):
    result=[]
    for category in CORE_FUNDS:
        sections=[s for s in rows(snapshot.get("sections")) if obj(s).get("section")==category]
        if len(sections)!=1 or sections[0].get("status")!="READY":continue
        report=obj(sections[0].get("result"))
        if report.get("category")!=category:continue
        shortlist=obj(report.get("historical_research_shortlist"));driver=obj(report.get("growth_driver_review"))
        if (shortlist.get("methodology")!="MF-MATCHED-PEER-1" or shortlist.get("status")!="HISTORICAL_SHORTLIST_AVAILABLE"
            or shortlist.get("category")!=category or not fresh(shortlist.get("last_date"),today,7)):continue
        drows=[d for d in rows(driver.get("items"))[:5] if isinstance(d,dict)] if driver.get("methodology")=="MF-QUARTERLY-DRIVERS-1" else []
        counts=Counter(r.get("identifier") for r in rows(shortlist.get("items"))[:5] if isinstance(r,dict) and isinstance(r.get("identifier"),str))
        detailed=rows(report.get("research_reports"))
        items=[]
        for r in rows(shortlist.get("items"))[:5]:
            if not isinstance(r,dict):continue
            code=r.get("identifier");day=r.get("nav_date")
            if (not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{5,8}",code) or counts[code]!=1
                or r.get("qualified") is not False or r.get("status")!="HISTORICAL_RESEARCH_ONLY"
                or day!=shortlist.get("last_date") or not named(r.get("name"))
                or not num(r.get("score"),50,100) or not num(r.get("weekly_cagr_percent"),.00001,1e6)):continue
            ds=[d for d in drows if d.get("identifier")==code]
            d=ds[0] if len(ds)==1 else {}
            matched=(d.get("qualified") is False and d.get("nav_date")==day and fresh(d.get("portfolio_date"),today,60)
                and fresh(d.get("quarter"),today,150) and num(d.get("joint_coverage_weight_percent"),70,100.5)
                and num(d.get("joint_growth_weight_percent"),0,d.get("joint_coverage_weight_percent",0))
                and num(d.get("review_weight_percent"),0,100.5))
            adverse=matched and (d.get("state")=="DRIVER_REVIEW_REQUIRED" or d["review_weight_percent"]>20 or d["joint_growth_weight_percent"]<50)
            positive=matched and not adverse and d.get("state")=="POSITIVE_HISTORICAL_DRIVERS_ONLY"
            reasons=[f"Matched historical peer score {r['score']:.1f}/100; three-year weekly-sampled CAGR {r['weekly_cagr_percent']:.1f}%."]
            if positive:reasons.append(f"Reported holdings with positive joint growth represent {d['joint_growth_weight_percent']:.1f}% of original fund weight.")
            if adverse:reasons.append("Underlying reported business trends require review.")
            growth=fund_growth(d,today) if matched else None
            facts={"historical_cagr_percent":r["weekly_cagr_percent"]}
            if matched:
                facts.update({k:d[k] for k in ("joint_coverage_weight_percent","joint_growth_weight_percent","review_weight_percent")})
            exact=[v for v in detailed if isinstance(v,dict) and v.get("identifier")==code and v.get("nav_date")==day and v.get("category")==category]
            context=research_synthesis.fund_context(r,exact[0] if len(exact)==1 else {},today)
            items.append({"fund_evidence":context,"identifier":code,"name":r["name"],"nav_date":day,"score":r["score"],
                "tier":"DRIVER_SUPPORTED" if positive else "DRIVER_REVIEW" if adverse else "HISTORICAL_ONLY",
                "action":"REVIEW_BEFORE_NEW_SIP" if adverse or context.get("ter_status")=="CONFLICTING_SAME_DATE_TER" else "COMPARE_FOR_SIP" if positive else "WATCH_FOR_CONFIRMATION",
                "relative_risk":r.get("relative_risk"),"reasons":reasons,"growth_outlook":growth,"observed_facts":facts,
                "evidence_confidence":"MODERATE" if positive and growth else "LIMITED" if positive else "LOW",
                "limitations":["Past returns and reported underlying growth do not establish future NAV returns.",
                    "Verify current official costs, holdings, benchmark and personal horizon."],"qualified":False})
        items.sort(key=lambda r:({"DRIVER_SUPPORTED":0,"HISTORICAL_ONLY":1,"DRIVER_REVIEW":2}[r["tier"]],-r["score"],r["identifier"]))
        result.append({"category":category,"items":items})
    return result

def analyze(snapshot,today,instant=None):
    out={"methodology":VERSION,"status":"DISABLED","research_date":today.isoformat(),"stocks":[],"funds":[],"next_steps":[],"notice":NOTICE}
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return out
    out["status"]="AWAITING_CURRENT_RESEARCH"
    if snapshot.get("research_date")!=today.isoformat():return out
    stocks=stock_projection(snapshot,instant);funds=fund_projection(snapshot,today)
    if instant is not None and stocks:
        from . import independent_valuation
        valuations=independent_valuation.read(instant,identities={r["isin"] for r in stocks})
        for row in stocks:
            v=valuations.get(row["isin"])
            if v and v["price_date"]==row["as_of"]:row["valuation_scenario"]=v
    for row in stocks:row["research_thesis"]=research_synthesis.thesis(row,False)
    for group in funds:
        for row in group["items"]:row["research_thesis"]=research_synthesis.thesis(row,True)
    out["multi_strategy"]=obj(snapshot.get("multi_strategy"))
    out.update(stocks=stocks,funds=funds,status="RESEARCH_AVAILABLE" if stocks or any(f["items"] for f in funds) else "NO_SUPPORTED_CANDIDATES")
    if stocks:out["next_steps"].append("Review the highest evidence-tier stock first; confirm current price and independent business evidence before allocating cash.")
    else:out["next_steps"].append("Do not force a new equity position from the current sample.")
    if any(r["tier"]=="DRIVER_SUPPORTED" for f in funds for r in f["items"]):out["next_steps"].append("Compare driver-supported funds within their own category and match risk and holding horizon before starting a SIP.")
    elif any(f["items"] for f in funds):out["next_steps"].append("Use fund peer leaders as a comparison list; future growth evidence is incomplete.")
    out["next_steps"].append("Review existing holdings and concentration before adding new capital; no personalized allocation inferred from public research.")
    return out
