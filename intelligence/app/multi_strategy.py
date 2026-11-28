"""Independent research lanes over the existing validated discovery sample.

Fixed, documented proxy rules. No model vote or observed match constitutes
strategy validation. Full academic factor portfolios require point-in-time data.
"""
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta
from math import isfinite,sqrt
from statistics import median,pstdev,mean
from zoneinfo import ZoneInfo
import re
from .replay_evidence import exact_isin
from .relative_strength import date_digest
from . import company_venues

VERSION="MULTI-STRATEGY-1"
NOTICE="Fixed research proxies, not canonical factor portfolios or verified trading signals. Correlated price signals count as one family. Independent prospective validation is required."
LANES={
    "FIP":"MOMENTUM","RELATIVE_STRENGTH":"MOMENTUM","RISK_ADJUSTED_MOMENTUM":"MOMENTUM",
    "TREND_FOLLOWING":"MOMENTUM","HIGH_52_WEEK":"MOMENTUM","CONTRACTION_PROXY":"MOMENTUM",
    "QUALITY_PROXY":"QUALITY","QUALITY_VALUE":"VALUE","PIOTROSKI_PARTIAL":"QUALITY",
    "EARNINGS_ACCELERATION":"GROWTH","GROWTH_LEADERSHIP_PROXY":"GROWTH",
    "SECTOR_MOMENTUM":"SECTOR","LOW_VOLATILITY":"DEFENSIVE",
    "DONCHIAN_BREAKOUT":"MOMENTUM","TURTLE_LONG_BREAKOUT":"MOMENTUM","STAGE2_PROXY":"MOMENTUM",
    "SEPA_TREND_TEMPLATE":"MOMENTUM","VCP_PROXY":"MOMENTUM","MEAN_REVERSION":"REVERSAL",
    "WYCKOFF_ACCUMULATION_PROXY":"REVERSAL","ANCHORED_VWAP_RECLAIM":"MOMENTUM",
    "GARP_PROXY":"VALUE","CAN_SLIM_PROXY":"GROWTH","PIOTROSKI_F_SCORE":"QUALITY",
    "QMJ_STYLE":"QUALITY","LOW_BETA":"DEFENSIVE","PEAD":"GROWTH"
}
def obj(v):return v if isinstance(v,dict) else {}
def rows(v):return v if isinstance(v,list) else []
def number(v,lo=-1e12,hi=1e12):return type(v) in (int,float) and isfinite(v) and lo<=v<=hi

def price_features(candles,calendar=()):
    """Compact observations only, using a completed contiguous suffix."""
    if len(candles)<201:return None
    sample=candles[-253:]
    dates=[c.date for c in sample]
    prices=[c.close for c in sample]
    if any(not number(p,.00001,1e9) for p in prices):return None
    if any(c.adjustment_status!=sample[-1].adjustment_status for c in sample):return None
    if sample[-1].adjustment_status not in ("ADJUSTED","RAW_UNADJUSTED"):return None
    changes=[b/a-1 for a,b in zip(prices,prices[1:])]
    if any(not number(v,-1,100) for v in changes):return None
    vol=pstdev(changes[-126:])*sqrt(252)*100
    turn=median(c.close*c.volume for c in sample[-20:])/1e7
    if not number(turn,0,1e12) or not number(vol,.00001,1e5):return None
    # Momentum excludes the latest 21 sessions (short-term reversal).
    r6=100*(prices[-22]/prices[-127]-1)
    r12=100*(prices[-22]/prices[-253]-1) if len(prices)==253 else None
    r60=100*(prices[-1]/prices[-61]-1)
    r200=100*(prices[-1]/prices[-201]-1)
    r252=100*(prices[-1]/prices[0]-1) if len(prices)==253 else None
    ranges=lambda s:(max(c.high for c in s)-min(c.low for c in s))/min(c.low for c in s)*100
    recent,prior=ranges(sample[-20:]),ranges(sample[-60:-20])
    from . import professional_strategies as pro
    patterns=pro.price_patterns(sample)
    return {"methodology":VERSION,"adjustment_status":sample[-1].adjustment_status,"professional_patterns":patterns,
        "calendar_matched":len(calendar)>=len(sample) and list(calendar[-len(sample):])==dates,
        "observations":len(sample),"first_date":dates[0],"last_date":dates[-1],
        "dates_digest":date_digest(dates[-127:]),"close":round(prices[-1],4),
        "turnover_cr":round(turn,4),"volatility_126_percent":round(vol,4),
        "momentum_6_ex_recent":round(r6,4),"momentum_12_ex_recent":round(r12,4) if r12 is not None else None,
        "return_60_percent":round(r60,4),"return_200_percent":round(r200,4),
        "return_252_percent":round(r252,4) if r252 is not None else None,
        "near_annual_high_percent":round(100*prices[-1]/max(c.high for c in sample),4) if len(sample)==253 else None,
        "above_sma200":prices[-1]>mean(prices[-200:]),"sma50_above_sma200":mean(prices[-50:])>mean(prices[-200:]),
        "range_20_percent":round(recent,4),"prior_range_40_percent":round(prior,4)}

def price_lanes(f):
    if not isinstance(f,dict) or f.get("methodology")!=VERSION:return []
    if not number(f.get("turnover_cr"),5,1e12):return []
    annual=f.get("return_252_percent")
    # Preserve the user's no-overextended-stock preference for trend leads.
    not_extended=number(annual,-100,99.9999) if annual is not None else number(f.get("return_200_percent"),-100,70)
    trend=not_extended and f.get("above_sma200") is True and f.get("sma50_above_sma200") is True and number(f.get("return_60_percent"),5,50)
    out=[]
    if trend:out.append("TREND_FOLLOWING")
    if trend and number(f.get("near_annual_high_percent"),90,100):out.append("HIGH_52_WEEK")
    if trend and number(f.get("range_20_percent"),0,12) and number(f.get("prior_range_40_percent"),8,100) and f["range_20_percent"]<=.6*f["prior_range_40_percent"]:
        out.append("CONTRACTION_PROXY")
    from . import professional_strategies as pro
    out.extend(pro.price_matches(f,not_extended))
    return out

def financial_lanes(report,today):
    """Conservative same-scope quality/value/acceleration evidence, not an imputed F-score."""
    quality=obj(report.get("fundamental_quality"));quarter=obj(report.get("quarterly_financials"))
    trends={r["metric"]:r for r in rows(obj(report.get("financial_trends")).get("items")) if isinstance(r,dict) and isinstance(r.get("metric"),str)
        and r.get("statement_type")=="consolidated" and r.get("period_basis")=="DECLARED_ANNUAL_MONTH_END" and r.get("latest_period_may_be_stale") is False}
    def matched(keys):
        t=[trends.get(k,{}) for k in keys]
        return all(number(r.get("latest_value")) and number(r.get("previous_value")) for r in t) and len({(r.get("latest_period"),r.get("previous_period"),str(r.get("unit")).lower()) for r in t})==1
    derived={r["metric"]:r for r in rows(quality.get("derived_metrics")) if isinstance(r,dict) and isinstance(r.get("metric"),str)}
    ratios={r["metric"]:r for r in rows(quality.get("sector_comparisons")) if isinstance(r,dict) and isinstance(r.get("metric"),str)}
    out=[];facts={}
    keys=("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW")
    if matched(keys):
        sales,profit,op,cash=(trends[k] for k in keys)
        if sales["previous_value"]>0 and profit["previous_value"]>0 and sales["latest_value"]>0:
            sales_growth=100*(sales["latest_value"]/sales["previous_value"]-1)
            profit_growth=100*(profit["latest_value"]/profit["previous_value"]-1)
            if number(sales_growth) and number(profit_growth):facts.update(sales_growth_percent=round(sales_growth,4),earnings_growth_percent=round(profit_growth,4))
        # Avoid a universal bank cash conversion rule: these are positive observed
        # business cash-flow checks, not a financial-sector solvency model.
        if (profit["latest_value"]>0 and op["latest_value"]>0 and cash["latest_value"]>=profit["latest_value"]
            and sales["latest_value"]>sales["previous_value"]>0 and profit["latest_value"]>=profit["previous_value"]>0
            and not quality.get("warnings")):
            out.append("QUALITY_PROXY")
            pe=ratios.get("PE",{});pb=ratios.get("PB",{})
            if all(number(r.get("company"),.0001,1e6) and number(r.get("sector"),.0001,1e6) and r["company"]<=r["sector"] for r in (pe,pb)):
                out.append("QUALITY_VALUE")
                facts.update(reported_pe=pe["company"],reported_sector_pe=pe["sector"])
    # Four observable Piotroski-like components only. No nine-point score.
    if matched(("NET_PROFIT","OPERATING_CASH_FLOW","TOTAL_ASSETS")):
        p,c,a=(trends[k] for k in ("NET_PROFIT","OPERATING_CASH_FLOW","TOTAL_ASSETS"))
        if a["latest_value"]>0 and a["previous_value"]>0:
            checks=[p["latest_value"]>0,c["latest_value"]>0,p["latest_value"]/a["latest_value"]>p["previous_value"]/a["previous_value"],c["latest_value"]>p["latest_value"]]
            facts["partial_quality_checks_passed"]=sum(checks)
            if all(checks):out.append("PIOTROSKI_PARTIAL")
    q={r.get("metric"):r for r in rows(quarter.get("items")) if isinstance(r,dict)}
    if quarter.get("status")=="REPORTED_QUARTERLY_COMPARISONS":
        try:age=(today-date.fromisoformat(quarter["latest_period"])).days
        except (ValueError,TypeError,KeyError):age=-1
        rev,profit=q.get("revenue",{}),q.get("net_profit",{})
        if 0<=age<=150 and all(number(r.get("year_over_year_growth_percent"),10,100) and number(r.get("growth_acceleration_pp"),2,100) for r in (rev,profit)):
            out.append("EARNINGS_ACCELERATION")
            facts["quarterly_profit_growth_percent"]=profit["year_over_year_growth_percent"]
            facts["quarterly_growth_acceleration_pp"]=profit["growth_acceleration_pp"]
    from . import professional_strategies as pro
    additional,extra=pro.financial_matches(report,today)
    out.extend(additional);facts.update(extra)
    return out,facts

def current_rows(snapshot,today):
    for s in rows(snapshot.get("sections")):
        if s.get("section") not in ("NSE","BSE") or s.get("status")!="READY":continue
        result=obj(s.get("result"));cov=obj(result.get("discovery_coverage"))
        if cov.get("calendar_checked_on")!=today.isoformat() or cov.get("calendar_status")!="PUBLISHED_SESSION":continue
        for r in rows(result.get("company_research_universe")):
            if not isinstance(r,dict) or r.get("exchange")!=s["section"] or r.get("as_of")!=cov.get("expected_session") or not exact_isin(r.get("isin")) or r.get("security_state") in company_venues.SPECIAL:continue
            try:
                if not 1<=(today-date.fromisoformat(r["as_of"])).days<=4:continue
            except (ValueError,TypeError):continue
            f=obj(r.get("multi_strategy_price"))
            if (f.get("methodology")==VERSION and f.get("last_date")==r["as_of"]
                and number(f.get("close"),.00001,1e9) and number(f.get("turnover_cr"),5,1e12)
                and type(r.get("id")) is int and r["id"]>0 and re.fullmatch(r"[A-Z0-9._&-]{1,50}",str(r.get("symbol","")))):
                yield r

def summarize(snapshot,connect,instant):
    from . import automatic_company_evidence as company,amfi_equity_caps,governance_review,sector_price_context,sector_benchmarks,relative_strength
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    result={"methodology":VERSION,"status":"AWAITING_EVIDENCE","items":[],"coverage":{},"lane_counts":{},"qualified":False,
        "unavailable_strategies":{"PEAD":"Timestamped pre-announcement consensus and actual earnings required",
        "QMJ_FULL":"Point-in-time cross-sectional profitability, growth, safety and payout factors required",
        "PIOTROSKI_FULL":"All nine matched annual inputs, including issuance, gross margin and leverage, required",
        "CAN_SLIM_FULL":"Quarterly share-adjusted EPS, institutional sponsorship and verified catalyst evidence required",
        "SEPA_FULL":"Complete audited earnings, growth and valuation evidence required beyond the trend template",
        "VCP_FULL":"Discretionary pattern definition; objective contraction proxy is implemented",
        "TURTLE_FULL":"Pyramiding, portfolio risk sizing and channel/ATR exits require a distinct portfolio simulator"},
        "notice":NOTICE}
    if snapshot.get("enabled") is not True:return result
    observations=company_venues.collect(snapshot,instant)
    caps=amfi_equity_caps.read(connect,today)
    chosen={}
    for r in current_rows(snapshot,today):
        isin=r["isin"];cap=caps.get(isin,{})
        if not number(cap.get("average_cap_cr"),1000,1e12):continue
        if any(v.get("security_state") in company_venues.SPECIAL for v in observations.get(isin,[])):continue
        f=r["multi_strategy_price"]
        rank=(r["as_of"],f.get("adjustment_status")=="ADJUSTED",f.get("calendar_matched") is True,r["exchange"]=="NSE",f["turnover_cr"],-r["id"])
        if isin not in chosen or rank>chosen[isin][0]:chosen[isin]=(rank,r)
    candidates=[v[1] for v in chosen.values()]
    reports=company.cached_action_reports(connect,list(chosen),instant)
    classifications=sector_price_context._classifications(connect,instant) if company.permitted() else {}
    indexes=obj(obj(snapshot.get("official_sector_benchmarks")).get("items"))
    regime=obj(snapshot.get("market_regime"))
    # Cohorts use identical dates and adjusted basis, not inconsistent windows.
    from . import professional_strategies as pro
    cohorts=defaultdict(list)
    for r in candidates:
        f=r["multi_strategy_price"]
        if f.get("calendar_matched") is True and f.get("adjustment_status")=="ADJUSTED" and number(f.get("volatility_126_percent"),.0001,1e5):
            cohorts[f["dates_digest"]].append(f)
    bounds={}
    for k,v in cohorts.items():
        if len(v)>=20:
            vols=sorted(x["volatility_126_percent"] for x in v)
            scores=sorted(x["momentum_6_ex_recent"]/x["volatility_126_percent"] for x in v if number(x.get("momentum_6_ex_recent")))
            if len(scores)>=20:bounds[k]=(vols[len(vols)//4],scores[3*len(scores)//4])
    # Compute QMJ-style cross-sectional percentiles once on current, comparable
    # financial cohorts. Missing components never receive neutral scores.
    prepared={}
    for r in candidates:
        isin=r["isin"];report=reports.get(isin,{})
        try:
            stamp=datetime.fromisoformat(report.get("retrieved_at",""))
            if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant:continue
            prepared[isin]=company._enrich(report,today,instant)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):continue
    qmj=pro.quality_ranks(prepared,classifications,today)
    from . import earnings_expectations
    surprises=earnings_expectations.read(instant)
    if surprises:
        result["unavailable_strategies"].pop("PEAD",None)
    result["expectations_evidence_basis"]="AUTHORIZED_OPERATOR_REVIEWED_IMPORT" if surprises else "NO_AUTHORIZED_EVENT_INPUT"
    counts=Counter();items=[]
    for r in candidates:
        f=r["multi_strategy_price"];isin=r["isin"];report=prepared.get(isin,{})
        if governance_review.assess(r,report,today)["findings"]:continue
        # Known company-level warnings in the established report remain authoritative.
        existing=obj(obj(obj(snapshot.get("company_reports")).get("items")).get(isin))
        if existing.get("review_findings"):continue
        lanes=price_lanes(f);facts={"return_60_percent":f["return_60_percent"],"median_daily_turnover_cr":f["turnover_cr"]}
        adjusted=f.get("adjustment_status")=="ADJUSTED" and f.get("calendar_matched") is True
        if adjusted:
            if obj(r.get("fip_research")).get("status")=="FIP_PRICE_MATCH" and number(f.get("return_252_percent"),0,99.9999):lanes.append("FIP")
            windows=obj(r.get("comparative_price_windows"));b=obj(regime.get("relative_strength_windows"))
            w=obj(windows.get("60"));ix=obj(b.get("60"))
            if (r["exchange"]=="NSE" and regime.get("as_of")==r["as_of"] and regime.get("calendar_checked_on")==today.isoformat()
                and w.get("source_code")=="UPSTOX" and isinstance(w.get("dates_digest"),str) and len(w["dates_digest"])==64
                and all(w.get(k)==ix.get(k) for k in ("dates_digest","first_date","last_date"))
                and number(w.get("return_percent"),5,50) and number(ix.get("return_percent"),-100,1e6) and w["return_percent"]>ix["return_percent"]):
                lanes.append("RELATIVE_STRENGTH")
            cap=bounds.get(f.get("dates_digest"))
            if cap and number(f.get("volatility_126_percent"),.0001,1e5) and number(f.get("momentum_6_ex_recent")):
                vol=f["volatility_126_percent"];mom=f["momentum_6_ex_recent"]
                if vol<=cap[0]:lanes.append("LOW_VOLATILITY")
                if mom>0 and mom/vol>=cap[1] and number(f.get("return_252_percent"),0,99.9999):lanes.append("RISK_ADJUSTED_MOMENTUM")
            sector=sector_benchmarks.compare(r,classifications.get(isin),indexes,today)
            sw=obj(obj(sector).get("windows")).get("60",{})
            if number(sw.get("index_return_percent"),5,100) and number(sw.get("difference_pp"),.0001,100):
                lanes.append("SECTOR_MOMENTUM")
        if report:
            financial,values=financial_lanes(report,today);lanes.extend(financial);facts.update(values)
            if "EARNINGS_ACCELERATION" in lanes and "HIGH_52_WEEK" in lanes and adjusted:lanes.append("GROWTH_LEADERSHIP_PROXY")
            if isin in qmj:
                facts["qmj_style_percentile"]=qmj[isin]
                if qmj[isin]>=75:lanes.append("QMJ_STYLE")
            if adjusted and "EARNINGS_ACCELERATION" in lanes and "SEPA_TREND_TEMPLATE" in lanes and "RELATIVE_STRENGTH" in lanes:
                lanes.append("CAN_SLIM_PROXY")
        if adjusted:
            event=surprises.get(isin)
            if event:
                # Require the earnings event to precede the completed price
                # session; no post-close same-day inference.
                release_day=datetime.fromisoformat(event["released_at"]).astimezone(ZoneInfo("Asia/Kolkata")).date()
                if release_day<date.fromisoformat(r["as_of"]):
                    surprise=pro.pead(event,instant)
                    if surprise is not None:
                        lanes.append("PEAD");facts["earnings_surprise_percent"]=surprise
            beta=pro.matched_beta(f,regime,r,today)
            if beta is not None:
                facts["historical_beta"]=beta
                if 0<=beta<=.75:lanes.append("LOW_BETA")
        # Unadjusted prices may be observed, but never pass price-only lanes.
        if not adjusted:lanes=[v for v in lanes if LANES[v] in ("QUALITY","VALUE","GROWTH") and v not in ("GROWTH_LEADERSHIP_PROXY","CAN_SLIM_PROXY","PEAD")]
        lanes=list(dict.fromkeys(lanes))
        if not lanes:continue
        families=sorted({LANES[v] for v in lanes})
        counts.update(lanes)
        plan=pro.strategy_risk_plan(f,lanes) if adjusted else None
        items.append({"id":r["id"],"isin":isin,"symbol":r["symbol"],"exchange":r["exchange"],"as_of":r["as_of"],
            "close":f["close"],"strategies":lanes,"families":families,"adjustment_verified_for_screen":adjusted,
            "observed_facts":facts,"price_volatility_percent":f["volatility_126_percent"],
            "risk":None,"price_plan":plan,"qualified":False,"status":"RESEARCH_MATCH_ONLY"})
    # Independent family breadth, not correlated-indicator voting. Regime is
    # a descriptive review lens only; no unvalidated regime performance claim.
    trend=regime.get("trend") if regime.get("as_of") in {r["as_of"] for r in candidates} else None
    def order(r):
        preferred={"QUALITY","VALUE","DEFENSIVE"} if trend=="FALLING" else {"MOMENTUM","GROWTH","SECTOR"} if trend=="RISING" else {"VALUE","REVERSAL","QUALITY"} if trend=="SIDEWAYS" else set()
        return (-len(r["families"]),-len(preferred.intersection(r["families"])),not r["adjustment_verified_for_screen"],-r["observed_facts"]["median_daily_turnover_cr"],r["isin"])
    items.sort(key=order)
    # Round-robin family coverage prevents a momentum-only top list.
    selected=[];seen=set()
    for family in ("QUALITY","VALUE","GROWTH","MOMENTUM","DEFENSIVE","SECTOR","REVERSAL"):
        row=next((r for r in items if family in r["families"] and r["isin"] not in seen),None)
        if row:selected.append(row);seen.add(row["isin"])
    selected.extend(r for r in items if r["isin"] not in seen)
    result.update(status="RESEARCH_AVAILABLE" if selected else "NO_SUPPORTED_MATCHES",items=selected[:10],
        coverage={"eligible_companies":len(candidates),"cached_company_reports":len(reports),"comparable_cohorts":len(bounds),"matched_companies":len(items)},
        lane_counts=dict(counts),regime=trend,regime_basis="DESCRIPTIVE_PRIORITY_ONLY",
        strategy_catalog=pro.catalog(counts,expectations_available=bool(surprises)))
    return result
