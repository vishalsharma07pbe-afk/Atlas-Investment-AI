"""Fixed-rule chronological replay of existing technical watches, not execution."""
from datetime import date, timedelta
from math import isfinite
from statistics import mean, median
from .technical import Candle, compute
from . import regime_features
from .horizon_research import evaluate, MIN_HISTORY, VERSION

WINDOWS = {"SWING":10,"SHORT_TERM":40,"LONG_TERM":120}
COSTS = (15, 30, 60)  # illustrative all-in bps per side, not actual broker charges

def _history(payload, today):
    rows=payload["candles"]
    candles=[]
    sources=set()
    previous=None
    for row in rows:
        day=date.fromisoformat(row["trade_date"])
        if day>=today:
            continue
        if previous and (day<=previous or (day-previous).days>7):
            raise ValueError("INVALID_DATES_OR_GAPS")
        previous=day
        if row.get("adjustment_status")!="ADJUSTED" or row.get("quality_status")!="PROVIDER_VALIDATED" or not row.get("source_code"):
            raise ValueError("ADJUSTED_VALIDATED_SOURCE_REQUIRED")
        sources.add(row["source_code"])
        o,h,l,c=(float(row[key]) for key in ("open","high","low","close"))
        v=int(row["volume"])
        if not all(isfinite(x) and x>0 for x in (o,h,l,c)) or l>min(o,c) or h<max(o,c) or v<0:
            raise ValueError("INVALID_OHLCV")
        candles.append(Candle(day.isoformat(),o,h,l,c,v,"ADJUSTED"))
    if len(sources)!=1:
        raise ValueError("MIXED_OR_MISSING_SOURCE")
    if not candles or (today-date.fromisoformat(candles[-1].date)).days>5:
        raise ValueError("STALE_HISTORY")
    return candles

def _metrics(trades, cost_bps):
    cost=cost_bps/10000
    equity=1.0
    peak=1.0
    drawdown=0.0
    benchmark=1.0
    returns=[]
    for entry,exit_price,closes in trades:
        start=equity
        shares=equity*(1-cost)/entry
        drawdown=min(drawdown,(shares*entry)/peak-1)
        for close in closes:
            marked=shares*close
            peak=max(peak,marked)
            drawdown=min(drawdown,marked/peak-1)
        equity=shares*exit_price*(1-cost)
        peak=max(peak,equity)
        drawdown=min(drawdown,equity/peak-1)
        benchmark*=exit_price/entry
        returns.append(equity/start-1)
    return {"cost_bps_per_side":cost_bps,"net_return_percent":round((equity-1)*100,4),
            "matched_gross_exposure_return_percent":round((benchmark-1)*100,4),
            "max_drawdown_percent":round(drawdown*100,4),
            "win_rate_percent":round(100*sum(x>0 for x in returns)/len(returns),2) if returns else None,
            "mean_trade_return_percent":round(mean(returns)*100,4) if returns else None,
            "wins":sum(x>0 for x in returns),"losses":sum(x<0 for x in returns),"flat":sum(x==0 for x in returns)}

def _comparison(trades,cost_bps,entry,exit_price):
    metrics=_metrics(trades,cost_bps)
    # Same holdout interval and starting capital. Buy and hold pays a single
    # round trip; strategy pays the stated cost per simulated position.
    reference=(exit_price/entry)*(1-cost_bps/10000)**2
    metrics["net_same_stock_buy_hold_percent"]=round((reference-1)*100,4)
    metrics["net_difference_vs_same_stock_pp"]=round(metrics["net_return_percent"]-(reference-1)*100,4)
    return metrics

REGIME_LOOKBACK=regime_features.LOOKBACK
REGIME_THRESHOLD=regime_features.TREND_THRESHOLD
REGIMES=("RISING","FALLING","SIDEWAYS","UNKNOWN")

def _market_regimes(equity,index,positions):
    """Classify at the signal close, never with subsequent index returns."""
    by_date={c.date:i for i,c in enumerate(equity)}
    index_dates=sorted(index)
    grouped={name:[] for name in REGIMES}
    for signal,trade in positions:
        regime="UNKNOWN"
        i=by_date.get(signal)
        if i is not None and i>=REGIME_LOOKBACK:
            dates=[c.date for c in equity[i-REGIME_LOOKBACK:i+1]]
            matched=[d for d in index_dates if dates[0]<=d<=signal]
            if dates==matched:
                change=(index[signal][1]/index[dates[0]][1]-1)*100
                if isfinite(change):
                    regime=("RISING" if change>=REGIME_THRESHOLD else
                            "FALLING" if change<=-REGIME_THRESHOLD else "SIDEWAYS")
        grouped[regime].append(trade)
    groups=[]
    for name,trades in grouped.items():
        scenarios=[]
        if trades and name!="UNKNOWN":
            for cost in COSTS:
                metrics=_metrics(trades,cost)
                scenarios.append({key:metrics[key] for key in
                    ("cost_bps_per_side","mean_trade_return_percent","win_rate_percent","wins","losses","flat")})
        groups.append({"regime":name,"trades":len(trades),"small_sample":len(trades)<30,"cost_scenarios":scenarios})
    classified=len(positions)-len(grouped["UNKNOWN"])
    return {"status":"MATCHED" if classified==len(positions) and classified else
            "PARTIAL" if classified else "UNAVAILABLE",
            "lookback_observations":REGIME_LOOKBACK,"threshold_percent":REGIME_THRESHOLD,
            "classified_trades":classified,"total_trades":len(positions),"groups":groups,
            "notice":"Illustrative Nifty 50 price trend at the signal close, not a forecast or a verified full market regime. Cohort means are per-position, not portfolio returns."}

def _attach_index_interval(interval,equity,index):
    interval["market_benchmark_status"]="UNAVAILABLE"
    for field in ("market_benchmark_start","market_benchmark_end","market_benchmark_observations"):
        interval.pop(field,None)
    for cost in interval["cost_scenarios"]:
        cost.pop("gross_nifty50_price_index_percent",None)
        cost.pop("net_difference_vs_nifty50_pp",None)
    dates=[c.date for c in equity if interval["test_start"]<c.date<=interval["test_end"]]
    if not dates or dates[-1]!=interval["test_end"]:
        return
    matched=sorted(d for d in index if dates[0]<=d<=dates[-1])
    if dates!=matched:
        return
    gross=(index[dates[-1]][1]/index[dates[0]][0]-1)*100
    if not isfinite(gross):
        return
    for cost in interval["cost_scenarios"]:
        cost["gross_nifty50_price_index_percent"]=round(gross,4)
        cost["net_difference_vs_nifty50_pp"]=round(cost["net_return_percent"]-gross,4)
    interval["market_benchmark_status"]="MATCHED_PRICE_INDEX"
    interval["market_benchmark_start"]=dates[0]
    interval["market_benchmark_end"]=dates[-1]
    interval["market_benchmark_observations"]=len(dates)

def price_index_history(benchmark,today):
    """Shared exact-source completed Nifty 50 price-index observation parser."""
    if not isinstance(benchmark,dict) or benchmark.get("benchmark_key")!="NSE_INDEX|Nifty 50" or benchmark.get("kind")!="PRICE_INDEX":
        raise ValueError("INDEX_IDENTITY")
    rows=benchmark["candles"]
    if not isinstance(rows,list) or len(rows)>400:
        raise ValueError("INDEX_HISTORY")
    index={}
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("INDEX_ROW")
        day=date.fromisoformat(row["trade_date"])
        if day>=today or day.isoformat() in index or row.get("source_code")!="UPSTOX":
            raise ValueError("INDEX_DATE_OR_SOURCE")
        if type(row.get("revision")) is not int or row["revision"]<1:
            raise ValueError("INDEX_REVISION")
        o,c=float(row["open"]),float(row["close"])
        if not all(isfinite(x) and x>0 for x in (o,c)):
            raise ValueError("INDEX_PRICE")
        index[day.isoformat()]=(o,c)
    return index


def attach_market_benchmark(result,payload,benchmark,today,*,positions=None):
    """Compare net simulation with the non-tradable Nifty 50 price index.

    Require exactly the same observed dates throughout the exposure interval;
    never interpolate missing dates or treat an absent index as a flat return.
    """
    try:
        equity=_history(payload,today)
        index=price_index_history(benchmark,today)
    except (ValueError,TypeError,KeyError,OverflowError):
        equity=[]
        index={}
    for name,horizon in result.get("horizons",{}).items():
        if horizon.get("status") not in ("REPLAY_OBSERVED","NO_SIGNALS"):
            continue
        if horizon["status"]=="NO_SIGNALS":
            for fold in horizon.get("chronological_validation",{}).get("folds",[]):
                if fold["status"]=="REPLAY_OBSERVED":
                    _attach_index_interval(fold,equity,index)
            continue
        horizon.pop("market_regime_research",None)
        horizon.pop("joint_regime_research",None)
        if positions is not None and len(positions.get(name,[]))==horizon["trades"]:
            horizon["market_regime_research"]=_market_regimes(equity,index,positions[name])
            horizon["joint_regime_research"]=_joint_regimes(equity,index,positions[name])
        _attach_index_interval(horizon,equity,index)
        for fold in horizon.get("chronological_validation",{}).get("folds",[]):
            if fold["status"]=="REPLAY_OBSERVED":
                _attach_index_interval(fold,equity,index)

LIQUIDITY_LOOKBACK=20
PARTICIPATION_LIMIT_PERCENT=0.5
REFERENCE_NOTIONALS=(100_000,500_000,1_000_000)
BASE_FRICTION_BPS=30
EXTRA_FRICTION_BPS=(0,25,75)

def _turnover_proxy(candle):
    # Same close-times-volume proxy used by the technical screener.
    # Adjusted prices and volumes need not reconstruct actual exchange turnover.
    value=candle.close*candle.volume
    return value if isfinite(value) and value>0 else None

def _prior_turnover(candles,at):
    values=[_turnover_proxy(c) for c in candles[max(0,at-LIQUIDITY_LOOKBACK):at]]
    if len(values)!=LIQUIDITY_LOOKBACK or any(v is None for v in values):
        return None
    return median(values)

def _execution_research(candles,signal_positions,hold):
    """Descriptive liquidity diagnostics and incremental friction stress.

    Do not remove historical positions based on their later observed volumes.
    Notionals are public fixed examples, not portfolio capital or order sizes.
    """
    by_date={c.date:i for i,c in enumerate(candles)}
    observations=[]
    for signal,trade in signal_positions:
        i=by_date[signal]
        entry=i+1
        exit_at=i+hold
        pre_entry=_prior_turnover(candles,entry)
        pre_exit=_prior_turnover(candles,exit_at)
        entry_day=_turnover_proxy(candles[entry])
        exit_day=_turnover_proxy(candles[exit_at])
        gross_ratio=trade[1]/trade[0]
        zero_volume=candles[entry].volume==0 or candles[exit_at].volume==0
        observations.append((pre_entry,pre_exit,entry_day,exit_day,gross_ratio,zero_volume))
    scenarios=[]
    for notional in REFERENCE_NOTIONALS:
        within=exceeded=unknown=0
        for pe,px,de,dx,ratio,zero_volume in observations:
            # An observed zero-volume endpoint contradicts the assumed fill.
            # Unknown evidence is not a pass and does not get imputed.
            if zero_volume:
                exceeded+=1
                continue
            exit_notional=notional*ratio
            if any(v is None for v in (pe,px,de,dx)) or not isfinite(exit_notional):
                unknown+=1
                continue
            participation=100*max(notional/pe,notional/de,exit_notional/px,exit_notional/dx)
            if participation>PARTICIPATION_LIMIT_PERCENT:
                exceeded+=1
            else:
                within+=1
        scenarios.append({"entry_notional_inr":notional,"within_proxy_limit":within,
                          "exceeds_proxy_limit":exceeded,"unknown":unknown})
    trades=[trade for _,trade in signal_positions]
    friction=[]
    for extra in EXTRA_FRICTION_BPS:
        if trades:
            cost=BASE_FRICTION_BPS+extra
            metrics=_metrics(trades,cost)
            friction.append({"extra_bps_per_side":extra,"total_bps_per_side":cost,
                             "net_return_percent":metrics["net_return_percent"],
                             "max_drawdown_percent":metrics["max_drawdown_percent"]})
    return {"status":"HISTORICAL_PROXY_ONLY" if trades else "NO_SIGNALS",
            "positions":len(trades),"lookback_observations":LIQUIDITY_LOOKBACK,
            "participation_limit_percent":PARTICIPATION_LIMIT_PERCENT,
            "zero_volume_endpoint_positions":sum(row[-1] for row in observations),
            "notional_scenarios":scenarios,"base_friction_bps_per_side":BASE_FRICTION_BPS,
            "friction_scenarios":friction,
            "notice":"Adjusted close × volume is only a historical proxy, not verified exchange turnover, executable open/close depth or capacity. Prior median and realized full-day observations are diagnostic only; later volume never selects or removes a replay position. Fixed INR examples are not recommended order sizes. Extra friction is illustrative, not calibrated slippage or verified fees/taxes."}

def _replay_interval(candles,signal_at,horizon,hold,start,end):
    """One closed test interval; no position may exit after its end."""
    trades=[]
    signal_positions=[]
    examined=0
    i=start
    while i+hold<=end:
        examined+=1
        if signal_at(i)[horizon][0]!="TECHNICAL_WATCH":
            i+=1
            continue
        entry=candles[i+1]
        exit_candle=candles[i+hold]
        trade=(entry.open,exit_candle.close,[c.close for c in candles[i+1:i+hold+1]])
        trades.append(trade)
        signal_positions.append((candles[i].date,trade))
        i+=hold
    return {"status":"REPLAY_OBSERVED" if trades else "NO_SIGNALS","trades":len(trades),
            "examined_signal_dates":examined,"holding_sessions":hold,"test_start":candles[start].date,
            "test_end":candles[end].date,
            "cost_scenarios":[_comparison(trades,cost,candles[start+1].open,candles[end].close) for cost in COSTS] if trades else [],
            "small_sample":len(trades)<30,
            "execution_research":_execution_research(candles,signal_positions,hold),
            "gross_buy_hold_percent":round((candles[end].close/candles[start+1].open-1)*100,4)},signal_positions

def _chronological_validation(candles,signal_at,horizon,hold,start,end):
    # At most three balanced consecutive folds. Exposure dates (start+1 to
    # end inclusive) never overlap; the previous closing bar can be the next
    # fold's first signal. A full holding window must fit in every fold.
    count=min(3,(end-start)//hold)
    result={"status":"INSUFFICIENT_REPEATED_WINDOWS","folds":[],"observed_folds":0,
            "eligible_folds":0,"no_signal_folds":0,"cost_summaries":[],
            "notice":"Fixed rules with expanding causal history; no fitting or parameter selection. Independent starting capital per fold, no exposure crossing boundaries. These historical partitions are not independent prospective tests."}
    if count<2:
        return result
    for f in range(count):
        left=start+(end-start)*f//count
        right=start+(end-start)*(f+1)//count
        fold,_=_replay_interval(candles,signal_at,horizon,hold,left,right)
        fold["fold"]=f+1
        fold["exposure_start"]=candles[left+1].date
        fold["prior_observations"]=left+1
        result["folds"].append(fold)
    observed=[f for f in result["folds"] if f["status"]=="REPLAY_OBSERVED"]
    result.update(status="REPEATED_WINDOWS_OBSERVED" if len(observed)>=2 else
                  "INSUFFICIENT_OBSERVED_FOLDS",eligible_folds=count,
                  observed_folds=len(observed),no_signal_folds=count-len(observed))
    for i,cost in enumerate(COSTS):
        if not observed:
            continue
        values=[f["cost_scenarios"][i]["net_return_percent"] for f in observed]
        result["cost_summaries"].append({"cost_bps_per_side":cost,
            "positive_folds":sum(v>0 for v in values),"negative_folds":sum(v<0 for v in values),
            "flat_folds":sum(v==0 for v in values),"worst_observed_return_percent":min(values),
            "best_observed_return_percent":max(values)})
    return result

def replay(payload, today, *, positions=None):
    try:
        candles=_history(payload,today)
    except (ValueError,TypeError,KeyError,OverflowError):
        return {"status":"EVIDENCE_GAP","horizons":{}}
    # Fixed existing rules, no fitting or tuning on either period. Chronological
    # split keeps the first 60% as warm-up/development context only.
    split=max(200,int(len(candles)*0.6))
    if split>=len(candles)-1:
        return {"status":"INSUFFICIENT_HISTORY","horizons":{}}
    ind=compute(candles)
    signals={}
    def signal_at(i):
        if i not in signals:
            signals[i]=evaluate(candles[:i+1],{k:v[:i+1] for k,v in ind.items()}, {})
        return signals[i]
    results={}
    for horizon,hold in WINDOWS.items():
        start=max(split,MIN_HISTORY[horizon]-1)
        if start+hold>=len(candles):
            results[horizon]={"status":"INSUFFICIENT_TEST_WINDOW","trades":0}
            continue
        result,signal_positions=_replay_interval(candles,signal_at,horizon,hold,start,len(candles)-1)
        result["chronological_validation"]=_chronological_validation(candles,signal_at,horizon,hold,start,len(candles)-1)
        if positions is not None:
            positions[horizon]=signal_positions
        results[horizon]=result
    return {"status":"HISTORICAL_REPLAY_ONLY","methodology":VERSION,
            "history_count":len(candles),"as_of":candles[-1].date,"horizons":results,
            "notice":"Fixed technical rules, chronological holdout, next-session open and fixed-session close. Costs are illustrative; cost-adjusted same-stock buy-and-hold uses the same test interval with one round trip; it and matched gross exposure are not market index benchmarks. Current registry selection and revised history can introduce bias. No validated forward performance or recommendation."}


def _joint_regimes(equity,index,positions):
    """Classify by information available at the signal, never by its outcome."""
    dates=[c.date for c in equity]
    by_date={d:i for i,d in enumerate(dates)}
    index_dates=sorted(index)
    def features(at):
        i=by_date.get(at)
        if i is None or i<REGIME_LOOKBACK:
            return None
        window=dates[i-REGIME_LOOKBACK:i+1]
        if window!=[d for d in index_dates if window[0]<=d<=at]:
            return None
        return regime_features.describe(window,[index[d][1] for d in window])
    groups={(trend,vol):[] for trend in ("RISING","FALLING","SIDEWAYS")
            for vol in ("HIGH_HISTORICAL_VOLATILITY","BELOW_HIGH_THRESHOLD")}
    unknown=0
    for signal,trade in positions:
        feature=features(signal)
        if feature is None:
            unknown+=1
        else:
            groups[(feature["trend"],feature["volatility_regime"])].append(trade)
    rows=[]
    for (trend,vol),trades in groups.items():
        costs=[]
        for cost in COSTS:
            if not trades:
                continue
            outcomes=[100*((exit_price/entry)*(1-cost/10000)**2-1) for entry,exit_price,_ in trades]
            # Within-position close-marked drawdown, not an equity curve
            # constructed by stitching disconnected historical episodes.
            drawdowns=[_metrics([trade],cost)["max_drawdown_percent"] for trade in trades]
            metrics=_metrics(trades,cost)
            costs.append({"cost_bps_per_side":cost,"mean_trade_return_percent":metrics["mean_trade_return_percent"],
                "median_trade_return_percent":round(median(outcomes),4),
                "worst_trade_return_percent":round(min(outcomes),4),
                "worst_position_drawdown_percent":min(drawdowns),
                "win_rate_percent":metrics["win_rate_percent"],"wins":metrics["wins"],
                "losses":metrics["losses"],"flat":metrics["flat"]})
        rows.append({"trend":trend,"volatility_regime":vol,"trades":len(trades),
                     "small_sample":len(trades)<30,"cost_scenarios":costs})
    classified=len(positions)-unknown
    latest=features(dates[-1]) if dates else None
    return {"status":"MATCHED" if classified and not unknown else "PARTIAL" if classified else "UNAVAILABLE",
            "methodology":regime_features.VERSION,"classified_trades":classified,"unknown_trades":unknown,
            "total_trades":len(positions),"groups":rows,
            "latest_benchmark_context":{**latest,"as_of":dates[-1]} if latest else None,
            "notice":"Signal-close trend and volatility from matched prior index dates only. After-cost position outcomes and worst within-position close-marked drawdown are descriptive, not a portfolio return, calibrated probability or validated regime-dependent strategy. Small and missing cohorts never qualify an investment."}
