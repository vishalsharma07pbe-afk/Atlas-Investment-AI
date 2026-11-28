"""Final decision-facing research policy, not investment certification.

Missing evidence is not a zero factor or a negative finding. Adverse evidence
cannot be outweighed by a high screen score or model agreement. No comparison
of scores across assets or evidence tiers, no probability or return estimates.
"""
from collections import Counter
from datetime import date
from math import isfinite

VERSION="FINAL-DECISION-QUALITY-1"
NOTICE="Evidence readiness and adverse findings, not return probability. Strongest cases remain conditional research; no execution or investment qualification."
def obj(x):return x if isinstance(x,dict) else {}
def rows(x):return x if isinstance(x,list) else []
def num(x,a,b):return type(x) in (int,float) and isfinite(x) and a<=x<=b
def fresh(day,today,lo,hi):
    try:return lo<=(today-date.fromisoformat(day)).days<=hi
    except (ValueError,TypeError):return False

def _status(row,checks,adverse):
    present=[k for k,v in checks.items() if v]
    missing=[k for k,v in checks.items() if not v]
    ai=obj(row.get("ai_review"))
    if ai.get("state") in ("DISAGREEMENT","DEFER_REVIEW"):adverse.append("INDEPENDENT_REVIEW_CAUTION")
    return {"methodology":VERSION,"state":"REVIEW_REQUIRED" if adverse else "PRIORITY_RESEARCH" if not missing else "EVIDENCE_INCOMPLETE",
        "supported_checks":present,"missing_checks":missing,"adverse_findings":sorted(set(adverse)),
        "evidence_checks_met":len(present),"evidence_checks_total":len(checks),
        "qualified":False,"notice":NOTICE}

def stock(row,today):
    f=obj(row.get("observed_facts"));g=obj(row.get("growth_outlook"));p=obj(row.get("price_plan"));v=obj(row.get("valuation_scenario"))
    reference=p.get("reference");stop=p.get("stop_scenario");target=p.get("target_scenario")
    risk_plan=all(num(x,.01,1e9) for x in (reference,stop,target,row.get("close"))) and stop<reference<target and abs(reference-row["close"])<=.0051
    pe=f.get("reported_pe");sector=f.get("reported_sector_pe")
    # Relative reported multiples are descriptive, not dated fair value.
    relative=num(pe,.01,40) and num(sector,.01,1e6)
    earnings=num(f.get("earnings_growth_percent"),10,100) and num(f.get("eps_growth_percent"),10,100)
    growth=num(g.get("revenue_yoy_percent"),-50,100) and num(g.get("profit_yoy_percent"),-50,100) and g.get("status")=="UNCALIBRATED_EARNINGS_SCENARIO"
    base=[x for x in rows(v.get("scenarios")) if isinstance(x,dict) and x.get("case")=="BASE"]
    valuation=(v.get("status")=="OPERATOR_SOURCE_BOUND_VALUATION_SCENARIO" and v.get("qualified") is False and v.get("isin")==row.get("isin")
        and v.get("price_date")==row.get("as_of") and len(base)==1 and num(base[0].get("upside_downside_percent"),-1e6,1e6))
    checks={"CURRENT_COMPLETED_SESSION":fresh(row.get("as_of"),today,1,4),
        "ADJUSTED_JOINT_SCREEN":row.get("tier")=="ADJUSTED_JOINT",
        "REPORTED_EARNINGS_AND_EPS_GROWTH":earnings,
        "REPORTED_RELATIVE_VALUATION":relative,
        "OBSERVED_LIQUIDITY":num(f.get("median_daily_turnover_cr"),5,1e10),
        "VALID_PRICE_RISK_SCENARIO":risk_plan,
        "CURRENT_QUARTER_SCENARIO":growth,
        "SOURCE_BOUND_VALUE_SCENARIO":valuation}
    adverse=[]
    if row.get("risk")=="HIGH":adverse.append("HIGH_HISTORICAL_PRICE_RISK")
    if relative and pe>sector:adverse.append("REPORTED_VALUATION_PREMIUM_REVIEW")
    if growth and min(g["revenue_yoy_percent"],g["profit_yoy_percent"])<=0:adverse.append("NONPOSITIVE_GROWTH_SCENARIO")
    if valuation and base[0]["upside_downside_percent"]<=0:adverse.append("BASE_VALUE_SCENARIO_NOT_ABOVE_REFERENCE")
    if not checks["CURRENT_COMPLETED_SESSION"]:adverse.append("STALE_PRICE_OBSERVATION")
    return _status(row,checks,adverse)

def fund(row,today):
    f=obj(row.get("fund_evidence"));g=obj(row.get("growth_outlook"));b=obj(f.get("benchmark_context"));facts=obj(row.get("observed_facts"))
    ter=f.get("ter_status")=="REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED" and num(f.get("ter_percent"),0,100) and fresh(f.get("ter_date"),today,0,7 if f.get("ter_basis")=="AMFI_WEBSITE_OPERATOR_CROSSWALK" else 90)
    tri=b.get("basis") in ("MATCHED_LOCAL_TRI_EXPORT","MATCHED_AUTHORIZED_DIRECT_TRI_CSV") and num(b.get("three_year_difference_pp"),-1e6,1e6) and num(b.get("rolling_outperformance_percent"),0,100)
    growth=g.get("status")=="UNCALIBRATED_UNDERLYING_GROWTH_SCENARIO" and num(g.get("coverage_percent"),70,100.5) and all(num(g.get(k),-50,100) for k in ("revenue_yoy_percent","profit_yoy_percent"))
    checks={"CURRENT_NAV":fresh(row.get("nav_date"),today,0,7),
        "MATCHED_PEER_HISTORY":num(row.get("score"),50,100) and num(facts.get("historical_cagr_percent"),.00001,1e6),
        "OBSERVED_DOWNSIDE_AND_VOLATILITY":num(f.get("weekly_drawdown_percent"),-100,0) and num(f.get("annualized_volatility_percent"),0,1e6),
        "SUPPORTED_UNDERLYING_DRIVERS":row.get("tier")=="DRIVER_SUPPORTED",
        "CURRENT_UNDERLYING_SCENARIO":growth,"MATCHED_DATED_TER":ter,"MATCHED_TRI_HISTORY":tri}
    adverse=[]
    if row.get("tier")=="DRIVER_REVIEW":adverse.append("UNDERLYING_BUSINESS_REVIEW")
    if f.get("ter_status")=="CONFLICTING_SAME_DATE_TER":adverse.append("CONFLICTING_FUND_EXPENSE_EVIDENCE")
    if growth and min(g["revenue_yoy_percent"],g["profit_yoy_percent"])<=0:adverse.append("NONPOSITIVE_UNDERLYING_SCENARIO")
    if tri and b["three_year_difference_pp"]<0 and b["rolling_outperformance_percent"]<50:adverse.append("PERSISTENT_MATCHED_BENCHMARK_LAG")
    if not checks["CURRENT_NAV"]:adverse.append("STALE_NAV_OBSERVATION")
    return _status(row,checks,adverse)

def attach(report,today):
    """Call after AI attachment so index-based committee bindings stay stable."""
    if report.get("status")!="RESEARCH_AVAILABLE":return report
    stocks=rows(report.get("stocks"));groups=rows(report.get("funds"))
    counts=Counter()
    def apply(items,kind):
        for r in items:
            q=stock(r,today) if kind=="STOCK" else fund(r,today)
            r["decision_quality"]=q
            counts[q["state"]]+=1
            # No positive override of the earlier action. Unknown evidence is
            # a watch, not a reason to manufacture a buy.
            if q["state"]=="REVIEW_REQUIRED":r["action"]="REVIEW_BEFORE_NEW_SIP" if kind=="FUND" else "WATCH_FOR_CONFIRMATION"
            elif q["state"]=="EVIDENCE_INCOMPLETE" and r.get("action") in ("RESEARCH_FOR_ENTRY","COMPARE_FOR_SIP"):r["action"]="WATCH_FOR_CONFIRMATION"
        # Stable within each evidence tier: no new performance score or cross-tier arithmetic.
        order={"PRIORITY_RESEARCH":0,"EVIDENCE_INCOMPLETE":1,"REVIEW_REQUIRED":2}
        tier_order={"ADJUSTED_JOINT":0,"REPORTED_JOINT":1,"BUSINESS_SCREEN":2,"MULTI_STRATEGY_RESEARCH":3,"TECHNICAL_LEAD":4,
                    "DRIVER_SUPPORTED":0,"HISTORICAL_ONLY":1,"DRIVER_REVIEW":2}
        items.sort(key=lambda r:(order[r["decision_quality"]["state"]],tier_order.get(r.get("tier"),99),-r["decision_quality"]["evidence_checks_met"]))
    apply(stocks,"STOCK")
    for g in groups:apply(rows(g.get("items")),"FUND")
    report["decision_quality"]={"methodology":VERSION,"counts":{k:counts[k] for k in ("PRIORITY_RESEARCH","EVIDENCE_INCOMPLETE","REVIEW_REQUIRED")},
        "qualified":False,"notice":NOTICE}
    if not counts["PRIORITY_RESEARCH"]:
        report["next_steps"]=["No complete priority-research case under the current evidence policy. Keep new capital uncommitted to these candidates; inspect the missing or adverse evidence first.",*rows(report.get("next_steps"))[1:]]
    return report
