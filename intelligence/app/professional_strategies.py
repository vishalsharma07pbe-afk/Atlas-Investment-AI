"""Explicit professional strategy adaptations; no unverified facts or claims of canonical results."""
from datetime import date,datetime,timedelta
from math import isfinite,sqrt
from statistics import mean,pstdev,median
from collections import defaultdict
from bisect import bisect_left,bisect_right
from .financial_strength import _block,_values,_recent_common
from .relative_strength import date_digest

def n(x,lo=-1e12,hi=1e12):return type(x) in (int,float) and isfinite(x) and lo<=x<=hi
def obj(v):return v if isinstance(v,dict) else {}
def price_patterns(s):
    if len(s)<201:return {}
    p=[c.close for c in s];v=[c.volume for c in s]
    if any(not n(c.low,.00001,1e9) or not n(c.high,c.low,1e9) or not n(c.volume,0,1e14) for c in s):return {}
    if any(not n(x,.00001,1e9) for x in p) or not n(mean(v[-21:-1]),.00001,1e14):return {}
    def span(a):return 100*(max(c.high for c in a)/min(c.low for c in a)-1)
    prior20=max(c.high for c in s[-21:-1]);prior55=max(c.high for c in s[-56:-1])
    # Anchor is defined before observing today's bar: most recent lowest low
    # in prior 60 completed sessions, never a retrospectively selected entry.
    anchor=len(s)-61+min(range(60),key=lambda i:s[-61+i].low)
    def avwap(a):
        den=sum(c.volume for c in a)
        return sum((c.high+c.low+c.close)/3*c.volume for c in a)/den if den>0 else None
    current,previous=avwap(s[anchor:]),avwap(s[anchor:-1])
    weekly=[p[i] for i in range(len(p)-1,-1,-5)][::-1]
    # 30 five-session close samples, not exchange calendar week-end candles.
    weekly_sma=mean(weekly[-30:]);prior_weekly=mean(weekly[-34:-4])
    sma200=mean(p[-200:]);prior200=mean(p[-221:-21]) if len(p)>=221 else None
    high=max(c.high for c in s[-252:]);low=min(c.low for c in s[-252:])
    volume_ratio=v[-1]/mean(v[-21:-1])
    recent=span(s[-10:]);middle=span(s[-30:-10]);older=span(s[-60:-30])
    sd=pstdev(p[-21:-1]);z=(p[-1]-mean(p[-21:-1]))/sd if sd else None
    ranges=[span(s[-61:-31]),span(s[-31:-1])]
    template_checks={"above_50_day":p[-1]>mean(p[-50:]),"50_above_150":mean(p[-50:])>mean(p[-150:]),
        "150_above_200":mean(p[-150:])>sma200,"rising_200":prior200 is not None and sma200>prior200,
        "above_annual_low_30_percent":len(s)>=252 and p[-1]>=1.3*low,
        "within_25_percent_of_annual_high":len(s)>=252 and p[-1]>=.75*high}
    contraction_checks={"older_range_percent":round(older,4),"middle_range_percent":round(middle,4),"recent_range_percent":round(recent,4),
        "recent_to_prior_volume":round(mean(v[-10:])/mean(v[-30:-10]),4) if mean(v[-30:-10])>0 else None,
        "prior_pivot":prior20,"pivot_confirmed":p[-1]>prior20 and volume_ratio>=1.5}
    return {"trend_template_checks":template_checks,"contraction_checks":contraction_checks,"channel_risk_inputs":channel_risk_inputs(s),"breakout20":p[-1]>prior20,"breakout55":p[-1]>prior55,"volume_ratio":round(volume_ratio,4),
        "stage2":p[-1]>weekly_sma>prior_weekly and p[-1]>prior55,
        "sepa_template":len(s)==253 and prior200 is not None and p[-1]>mean(p[-50:])>mean(p[-150:])>sma200>prior200 and p[-1]>=1.3*low and p[-1]>=.75*high,
        "vcp":older>middle>recent and middle<=.8*older and recent<=.8*middle and mean(v[-10:])<.8*mean(v[-30:-10]) and p[-1]>=.95*max(c.high for c in s[-60:]),
        "mean_reversion":z is not None and z<=-2 and p[-1]>sma200 and p[-1]<p[-2],
        "wyckoff":ranges[1]<.65*ranges[0] and p[-1]>prior20 and volume_ratio>=1.5 and p[-1]>sma200,
        "avwap_reclaim":current is not None and previous is not None and p[-2]<=previous and p[-1]>current and volume_ratio>=1,
        "beta_dates_digest":date_digest([c.date for c in s[-61:]]),
        "beta_returns":[round(b/a-1,9) for a,b in zip(p[-61:-1],p[-60:])]}

def channel_risk_inputs(candles):
    """Completed-session Wilder N and causal channels, not execution quotes."""
    if len(candles)<56:return None
    if any(not n(c.close,.00001,1e9) or not n(c.low,.00001,c.close)
           or not n(c.high,c.close,1e9) for c in candles):return None
    tr=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close))
        for a,b in zip(candles,candles[1:])]
    atr=mean(tr[:20])
    for value in tr[20:]:atr=(19*atr+value)/20
    if not n(atr,.00001,1e9):return None
    return {"n":atr,"close":candles[-1].close,
        "entry20":max(c.high for c in candles[-21:-1]),
        "entry55":max(c.high for c in candles[-56:-1]),
        "exit10":min(c.low for c in candles[-10:]),
        "exit20":min(c.low for c in candles[-20:]),
        "mean20":mean(c.close for c in candles[-21:-1])}

def strategy_risk_plan(features,strategies):
    """Conditional price geometry, not a forecast or an execution signal."""
    if features.get("adjustment_status")!="ADJUSTED" or features.get("calendar_matched") is not True:return None
    a=obj(obj(features.get("professional_patterns")).get("channel_risk_inputs"))
    close,atr=a.get("close"),a.get("n")
    if not n(close,.01,1e8) or not n(atr,.00001,1e9) or atr/close>.05:return None
    if not n(features.get("close"),.01,1e8) or abs(features["close"]-close)>.000051:return None
    for rule in ("TURTLE_LONG_BREAKOUT","DONCHIAN_BREAKOUT","MEAN_REVERSION","VCP_PROXY","STAGE2_PROXY","SEPA_TREND_TEMPLATE","TREND_FOLLOWING"):
        if rule not in strategies:continue
        if rule in ("TURTLE_LONG_BREAKOUT","DONCHIAN_BREAKOUT"):
            turtle=rule=="TURTLE_LONG_BREAKOUT"
            trigger=a.get("entry55" if turtle else "entry20")
            channel=a.get("exit20" if turtle else "exit10")
            if not n(trigger,.01,close) or not n(channel,.01,close) or trigger>=close:continue
            stop=close-2*atr if turtle else max(close-2*atr,channel)
            exit_rule="20_SESSION_LOW_OR_2N_STOP" if turtle else "10_SESSION_LOW_OR_2ATR_STOP"
            target=close+2*(close-stop)
        elif rule=="MEAN_REVERSION":
            trigger=close;stop=close-2*atr;target=a.get("mean20")
            exit_rule="PRIOR_20_SESSION_MEAN_OR_2ATR_STOP"
            if not n(target,close,1e9):continue
        else:
            trigger=close;low=a.get("exit10")
            if not n(low,.01,close):continue
            stop=max(close-2*atr,low);target=close+2*(close-stop)
            exit_rule="RECENT_10_SESSION_LOW_OR_2ATR_STOP"
        entry,stop,target=round(close,2),round(stop,2),round(target,2)
        if not 0<stop<entry<target:continue
        risk=entry-stop
        result={"reference":entry,"entry_trigger":round(trigger,2),"stop_scenario":stop,
            "target_scenario":target,"reward_risk":round((target-entry)/risk,2),
            "method":"STRATEGY_RISK_GEOMETRY_V1","strategy":rule,"exit_rule":exit_rule,
            "n_or_atr":round(atr,4),"risk_per_share":round(risk,2),
            "risk_percent":round(100*risk/entry,4),"qualified":False,
            "notice":"Prior-close research scenario only; target is illustrative, not fair value or a forecast. Recheck live spread, gaps, costs and corporate actions."}
        if rule=="TURTLE_LONG_BREAKOUT":
            result.update(channel_exit=round(channel,2),hypothetical_add_interval=round(.5*atr,4),
                notice="Turtle channel exit has no fixed profit target; the displayed 2R target is comparison geometry only. No fills or portfolio allocation inferred.")
        return result
    return None

def turtle_unit_size(capital,atr,entry,available_cash,risk_budget_percent=1):
    """Conservative cash-only hypothetical unit, not an order quantity."""
    if not all(n(v,.01,1e12) for v in (capital,atr,entry)) or not n(available_cash,0,capital) or not n(risk_budget_percent,.01,1):return None
    shares=int(min(capital*risk_budget_percent/100/(2*atr),available_cash/entry))
    return {"shares":shares,"initial_stop_risk":round(shares*2*atr,2),
        "notional":round(shares*entry,2),"qualified":False}

def price_matches(f,not_extended):
    a=obj(f.get("professional_patterns"));out=[]
    if not not_extended:return out
    if a.get("breakout20") is True and n(a.get("volume_ratio"),1.2,1e6):out.append("DONCHIAN_BREAKOUT")
    if a.get("breakout55") is True:out.append("TURTLE_LONG_BREAKOUT")
    if a.get("stage2") is True:out.append("STAGE2_PROXY")
    if a.get("sepa_template") is True:out.append("SEPA_TREND_TEMPLATE")
    if a.get("vcp") is True and f.get("above_sma200") is True:out.append("VCP_PROXY")
    if a.get("mean_reversion") is True:out.append("MEAN_REVERSION")
    if a.get("wyckoff") is True:out.append("WYCKOFF_ACCUMULATION_PROXY")
    if a.get("avwap_reclaim") is True and f.get("above_sma200") is True:out.append("ANCHORED_VWAP_RECLAIM")
    return out

def matched_beta(f,regime,r,today):
    a=obj(f.get("professional_patterns"));b=obj(regime.get("beta_window"))
    if r.get("exchange")!="NSE" or regime.get("as_of")!=r.get("as_of") or regime.get("calendar_checked_on")!=today.isoformat() or not isinstance(a.get("beta_dates_digest"),str) or a["beta_dates_digest"]!=b.get("dates_digest"):return None
    x,y=a.get("beta_returns"),b.get("returns")
    if not isinstance(x,list) or not isinstance(y,list) or len(x)!=60 or len(y)!=60 or not all(n(z,-1,100) for z in x+y):return None
    vx=pstdev(y)**2
    if vx<=1e-12:return None
    a0,b0=mean(x),mean(y)
    beta=mean((i-a0)*(j-b0) for i,j in zip(x,y))/vx
    return round(beta,4) if n(beta,-100,100) else None

def annual_inputs(report,today):
    """Exact normalized line items; no substitution of total liability for debt,
    net financing for share issuance or operating profit for gross profit."""
    income,_=_block(report,"income_statement");cash,_=_block(report,"cash_flow");balance,_=_block(report,"balance_sheet")
    def values(data,field,name):return _values(data,field,name,today)
    def assets():
        from .financial_trends import _series,_label
        points=_series([{"period":r.get("period"),"value":r.get("total_asset")} for r in balance.get("rows",[])],today,True)
        return {_label(p):v for p,v in (points or []) if p[1] and n(v,.00001,1e12)}
    return {"profit":values(income,"rows","net_profit") or values(income,"rows","net profit"),
        "revenue":values(income,"rows","revenue"),"cash":values(cash,"rows","operating"),"assets":assets(),
        "gross_profit":values(income,"detail_rows","gross profit"),
        "long_debt":values(balance,"detail_rows","long term borrowings"),
        "current_assets":values(balance,"detail_rows","current assets"),
        "current_liabilities":values(balance,"detail_rows","current liabilities"),
        "issuance":values(cash,"detail_rows","proceeds from issue of equity shares"),
        "dividends":values(cash,"detail_rows","dividends paid"),
        "repurchases":values(cash,"detail_rows","repurchase of equity shares")}

def piotroski(inputs,today):
    # Beginning assets used for ROA, leverage and turnover. Need three
    # consecutive asset observations and matched latest annual periods.
    keys=("profit","revenue","cash","assets","gross_profit","long_debt","current_assets","current_liabilities","issuance")
    periods=_recent_common([inputs.get(k,{}) for k in keys],today)
    if len(periods)<2:return None
    a,b=periods[-2:];prev=str(int(a[:4])-1)+a[4:]
    get=lambda k,p:inputs[k][p]
    if prev not in inputs["assets"]:return None
    assets=[get("assets",p) for p in (prev,a,b)]
    if not all(n(z,.00001,1e12) for z in assets):return None
    if not all(n(get(k,p),.00001,1e12) for k in ("revenue","current_liabilities") for p in (a,b)):return None
    if not all(n(get(k,p),0,1e12) for k in ("current_assets","long_debt","issuance") for p in (a,b)):return None
    roa=get("profit",b)/assets[1];prior=get("profit",a)/assets[0];cfo=get("cash",b)/assets[1]
    checks={"positive_roa":roa>0,"positive_cfo":cfo>0,"roa_improving":roa>prior,"cash_exceeds_profit":cfo>roa,
        "leverage_declining":get("long_debt",b)/mean(assets[1:])<get("long_debt",a)/mean(assets[:2]),
        "liquidity_improving":get("current_assets",b)/get("current_liabilities",b)>get("current_assets",a)/get("current_liabilities",a),
        "no_equity_issuance":get("issuance",b)==0,
        "gross_margin_improving":get("gross_profit",b)/get("revenue",b)>get("gross_profit",a)/get("revenue",a),
        "asset_turnover_improving":get("revenue",b)/assets[1]>get("revenue",a)/assets[0]}
    return {"score":sum(checks.values()),"checks":checks,"period":b}

def financial_matches(report,today):
    out=[];facts={}
    inputs=annual_inputs(report,today)
    score=piotroski(inputs,today)
    if score:
        facts["piotroski_score"]=score["score"]
        facts["piotroski_checks"]=score["checks"]
        facts["piotroski_period"]=score["period"]
        if score["score"]>=7:out.append("PIOTROSKI_F_SCORE")
    trends=obj(report.get("financial_trends")).get("items",[])
    profit=next((r for r in trends if r.get("metric")=="NET_PROFIT" and r.get("latest_period_may_be_stale") is False and r.get("period_basis")=="DECLARED_ANNUAL_MONTH_END" and r.get("statement_type")=="consolidated"),{})
    quality=obj(report.get("fundamental_quality"))
    pe=next((r for r in quality.get("sector_comparisons",[]) if r.get("metric")=="PE"),{})
    growth=profit.get("cagr_3y_percent")
    # Historical profit CAGR is not forecast EPS growth; this is a PEG-like proxy.
    if n(growth,10,40) and n(pe.get("company"),.0001,40) and n(pe.get("sector"),.0001,1e6) and pe["company"]<=pe["sector"] and pe["company"]/growth<=1.5 and not quality.get("warnings"):
        out.append("GARP_PROXY");facts["historical_profit_growth_to_pe_proxy"]=round(pe["company"]/growth,4)
    return out,facts

def quality_components(report,today):
    a=annual_inputs(report,today);keys=("profit","revenue","cash","assets","long_debt","dividends","repurchases","issuance")
    common=_recent_common([a[k] for k in keys],today)
    if len(common)<2:return None
    x,y=common[-2:]
    if any(not n(a[k][p],.00001,1e12) for k in ("assets","revenue","profit") for p in (x,y)):return None
    if any(not n(a[k][p],0,1e12) for k in ("long_debt","issuance") for p in (x,y)):return None
    # Cash-flow sign of payments must be explicitly negative or zero.
    if any(not n(a[k][y],-1e12,0) for k in ("dividends","repurchases")):return None
    return y,(a["profit"][y]/a["assets"][x]+a["cash"][y]/a["assets"][x],
        a["profit"][y]/a["profit"][x]-1,
        -a["long_debt"][y]/a["assets"][y],
        (-a["dividends"][y]-a["repurchases"][y]-a["issuance"][y])/a["assets"][x])

def quality_ranks(reports,classifications,today):
    cohorts=defaultdict(list)
    for isin,report in reports.items():
        labels=classifications.get(isin)
        if not labels or not labels[0]:continue
        item=quality_components(report,today)
        if item:cohorts[(labels[0],item[0])].append((isin,item[1]))
    result={}
    for cohort in cohorts.values():
        if len(cohort)<20:continue
        columns=[sorted(v[j] for _,v in cohort) for j in range(4)]
        for isin,v in cohort:
            ranks=[50*(bisect_left(columns[j],v[j])+bisect_right(columns[j],v[j]))/len(cohort) for j in range(4)]
            result[isin]=round(mean(ranks),2)
    return result

def pead(event,instant):
    """Contract for genuine surprise evidence; no model-generated consensus,
    no latest-quarter growth substitution. Only real pre-release estimates."""
    try:
        expected=event["consensus_eps"];actual=event["actual_eps"]
        captured=datetime.fromisoformat(event["consensus_as_of"]);release=datetime.fromisoformat(event["released_at"])
        if not (event.get("consensus_verified") is True and event.get("release_verified") is True and event.get("same_share_basis") is True
            and type(event.get("analyst_count")) is int and event["analyst_count"]>=3
            and captured.tzinfo and release.tzinfo and captured<release<instant<=release+timedelta(days=30)
            and release-captured<=timedelta(days=90) and n(expected,.01,1e6) and n(actual,.01,1e6)):return None
        surprise=100*(actual/expected-1)
        return round(surprise,4) if n(surprise,5,100) else None
    except (ValueError,TypeError,KeyError,OverflowError):return None

def catalog(counts,expectations_available=False):
    from .multi_strategy import LANES
    partial={"QUALITY_PROXY","PIOTROSKI_PARTIAL","QUALITY_VALUE","QMJ_STYLE","GARP_PROXY","GROWTH_LEADERSHIP_PROXY","CAN_SLIM_PROXY","SEPA_TREND_TEMPLATE","VCP_PROXY","CONTRACTION_PROXY","STAGE2_PROXY","TURTLE_LONG_BREAKOUT","WYCKOFF_ACCUMULATION_PROXY","ANCHORED_VWAP_RECLAIM"}
    return {k:{"status":"MATCHED_RESEARCH" if counts.get(k) else "AWAITING_VERIFIED_EXPECTATIONS_FEED" if k=="PEAD" and not expectations_available else "NO_MATCH_OR_INSUFFICIENT_EVIDENCE",
        "matches":counts.get(k,0),"implementation":"EVIDENCE_GATED_RULE" if k=="PEAD" else "FIXED_ADAPTATION" if k in partial else "FIXED_RESEARCH_RULE","qualified":False} for k in LANES}
