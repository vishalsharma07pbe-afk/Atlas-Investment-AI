"""Fixed rule price-strategy replay on verified local inputs.

The worker invokes this only after full-manifest, listing, revision, action
and stored-session checks. No financial-factor historical simulation without
point-in-time fundamentals and historical constituent membership.
"""
from datetime import date
from math import isfinite,sqrt
from statistics import mean,pstdev
from . import multi_strategy as m, strategy_validation as sv, fip_research, regime_features

VERSION="MULTI-STRATEGY-REPLAY-1"
LANES=("FIP","TREND_FOLLOWING","HIGH_52_WEEK","CONTRACTION_PROXY","DONCHIAN_BREAKOUT","TURTLE_LONG_BREAKOUT","STAGE2_PROXY","SEPA_TREND_TEMPLATE","VCP_PROXY","MEAN_REVERSION","WYCKOFF_ACCUMULATION_PROXY","ANCHORED_VWAP_RECLAIM")
HOLD=20
FOLD=63
COSTS=(15,30,60)
NOTICE=("Fixed, untuned price rules; chronological holdout and nonoverlapping test folds. "
        "Next-session open entry, 20-session close exit, illustrative all-in per-side costs, "
        "cash between positions, zero risk-free rate. Price-index comparison excludes dividends. "
        "Current registry and revised history create survivorship and point-in-time bias; not a validated portfolio backtest.")

def signals(candles,i):
    s=candles[i-252:i+1]
    if len(s)!=253:return set()
    f=m.price_features(s,[v.date for v in s])
    if f is None:return set()
    out=set(m.price_lanes(f))
    e=fip_research.metrics([v.close for v in s],[v.volume for v in s])
    if e and e.get("status")=="FIP_PRICE_MATCH" and m.number(f.get("return_252_percent"),0,99.9999):out.add("FIP")
    return out

def metrics(candles,start,end,positions,bps):
    # start and end are inclusive test-day indices; signals originate no
    # earlier than start-1. Trade entry at next open, mark every close.
    equity=1.;path=[1.];trades=[];cost=bps/10000
    by_entry={i+1:i+HOLD for i in positions}
    shares=0.;exit_at=-1;before=1.
    for i in range(start,end+1):
        c=candles[i]
        if i in by_entry:
            before=equity;shares=equity*(1-cost)/c.open;exit_at=by_entry[i]
        if shares:
            equity=shares*c.close
            if i==exit_at:
                equity*=1-cost
                trades.append(equity/before-1);shares=0.
        path.append(equity)
    changes=[b/a-1 for a,b in zip(path,path[1:])]
    peak=1.;dd=0.
    for v in path:
        peak=max(peak,v);dd=min(dd,v/peak-1)
    sigma=pstdev(changes) if len(changes)>=2 else 0.
    downside=sqrt(mean([min(0,r)**2 for r in changes])) if changes else 0.
    days=(date.fromisoformat(candles[end].date)-date.fromisoformat(candles[start].date)).days+1
    # Short folds have no annualized CAGR; the long holdout may have one.
    cagr=(equity**(365.25/days)-1)*100 if days>=365 and equity>0 else None
    gain=sum(x for x in trades if x>0);loss=-sum(x for x in trades if x<0)
    def rounded(x):return round(x,6) if x is not None and isfinite(x) else None
    return {"cost_bps_per_side":bps,"sessions":len(changes),"trades":len(trades),
        "net_return_percent":rounded(100*(equity-1)),"cagr_percent":rounded(cagr),
        "annualized_sharpe_rf_zero":rounded(mean(changes)/sigma*sqrt(252)) if sigma else None,
        "annualized_sortino_rf_zero":rounded(mean(changes)/downside*sqrt(252)) if downside else None,
        "max_drawdown_percent":rounded(dd*100),"win_rate_percent":rounded(100*sum(x>0 for x in trades)/len(trades)) if trades else None,
        "profit_factor":rounded(gain/loss) if loss else None,"trade_returns_percent":[rounded(x*100) for x in trades]}

def positions_for(signal_map,lane,start,end):
    result=[];next_signal=start-1
    for i in range(start-1,end-HOLD+1):
        if i>=next_signal and lane in signal_map.get(i,set()):
            result.append(i);next_signal=i+HOLD
    return result

def pearson(a,b):
    if len(a)!=len(b) or len(a)<4:return None
    x,y=pstdev(a),pstdev(b)
    if not x or not y:return None
    return round(max(-1.,min(1.,mean([(i-mean(a))*(j-mean(b)) for i,j in zip(a,b)])/(x*y))),6)

def replay(payload,benchmark,today):
    try:c=sv._history(payload,today)
    except (ValueError,TypeError,KeyError,OverflowError):return {"status":"EVIDENCE_GAP"}
    if len(c)<253+FOLD:return {"status":"INSUFFICIENT_HISTORY","history_count":len(c)}
    try:index=sv.price_index_history(benchmark,today)
    except (ValueError,TypeError,KeyError,OverflowError):index={}
    start=max(253,int(len(c)*.6));end=len(c)-1
    if end-start+1<FOLD:return {"status":"INSUFFICIENT_TEST_WINDOW","history_count":len(c)}
    signal_map={i:signals(c,i) for i in range(start-1,end-HOLD+1)}
    folds=[(i,min(i+FOLD-1,end)) for i in range(start,end+1,FOLD) if end-i+1>=FOLD]
    def benchmark_return(a,z):
        if all(v.date in index for v in c[a:z+1]):
            return round((index[c[z].date][1]/index[c[a].date][0]-1)*100,6)
        return None
    def regime(i):
        labels=[v.date for v in c[i-60:i+1]]
        if len(labels)!=61 or any(d not in index for d in labels):return "UNKNOWN"
        f=regime_features.describe(labels,[index[d][1] for d in labels])
        return f["trend"] if f else "UNKNOWN"
    lanes={};fold_values={}
    for lane in LANES:
        p=positions_for(signal_map,lane,start,end)
        report={"cost_scenarios":[metrics(c,start,end,p,b) for b in COSTS],
                "gross_nifty50_price_index_percent":benchmark_return(start,end),"folds":[],"signal_regimes":{}}
        for a,z in folds:
            q=positions_for(signal_map,lane,a,z)
            v=metrics(c,a,z,q,30)
            report["folds"].append({"start":c[a].date,"end":c[z].date,**v,"gross_nifty50_price_index_percent":benchmark_return(a,z)})
        fold_values[lane]=[f["net_return_percent"] for f in report["folds"]]
        for group in ("RISING","FALLING","SIDEWAYS","UNKNOWN"):
            cohort=[i for i in p if regime(i)==group]
            returns=[((c[i+HOLD].close/c[i+1].open)*(1-.003)**2-1)*100 for i in cohort]
            report["signal_regimes"][group]={"trades":len(returns),"mean_net_trade_return_percent":round(mean(returns),6) if returns else None,"small_sample":len(returns)<30}
        lanes[lane]=report
    correlation=[]
    for i,a in enumerate(LANES):
        for b in LANES[i+1:]:
            x=pearson(fold_values[a],fold_values[b])
            if x is not None:correlation.append({"a":a,"b":b,"fold_return_correlation":x,"folds":len(folds)})
    return {"methodology":VERSION,"status":"DESCRIPTIVE_REPLAY_ONLY","as_of":c[-1].date,
        "history_count":len(c),"history_start":c[0].date,"test_start":c[start].date,"test_end":c[end].date,
        "full_folds":len(folds),"lanes":lanes,"fold_correlation":correlation,"qualified":False,
        "historical_universe_verified":False,"total_return_benchmark_verified":False,"notice":NOTICE}

def summarize(payloads,today):
    # Per-instrument simulations are not portfolio backtests. Report sample
    # counts rather than aggregate compounding of overlapping capital.
    seen=set();counts={lane:{"companies":0,"trades":0,"positive_holdout_companies":0,"matched_price_index_companies":0} for lane in LANES}
    for p in payloads:
        report=p.get("multi_strategy_replay") or {}
        identity=p.get("isin")
        try:
            if not m.exact_isin(identity) or identity in seen or report.get("methodology")!=VERSION or report.get("status")!="DESCRIPTIVE_REPLAY_ONLY" or not 1<=(today-date.fromisoformat(report["as_of"])).days<=5:continue
        except (ValueError,TypeError,KeyError):continue
        seen.add(identity)
        for lane in LANES:
            r=report.get("lanes",{}).get(lane,{})
            scenarios=r.get("cost_scenarios",[])
            v=next((v for v in scenarios if v.get("cost_bps_per_side")==30),{})
            if not v:continue
            counts[lane]["companies"]+=1;counts[lane]["trades"]+=v["trades"]
            if v["net_return_percent"]>0:counts[lane]["positive_holdout_companies"]+=1
            if r.get("gross_nifty50_price_index_percent") is not None:counts[lane]["matched_price_index_companies"]+=1
    return {"methodology":VERSION,"status":"DESCRIPTIVE_SAMPLE_AVAILABLE" if seen else "AWAITING_REPLAY",
            "companies":len(seen),"lanes":counts,"qualified":False,"notice":NOTICE,
            "blockers":["FIVE_TO_TEN_YEAR_HISTORY_REQUIRED","HISTORICAL_CONSTITUENT_MEMBERSHIP_REQUIRED",
            "POINT_IN_TIME_FINANCIALS_REQUIRED","TOTAL_RETURN_BENCHMARK_REQUIRED","PORTFOLIO_WALK_FORWARD_REQUIRED","PROSPECTIVE_VALIDATION_REQUIRED"]}
