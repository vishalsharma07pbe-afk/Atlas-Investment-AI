"""Fixed-rule chronological replay of existing technical watches, not execution."""
from datetime import date, timedelta
from math import isfinite
from statistics import mean
from .technical import Candle, compute
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

def replay(payload, today):
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
    results={}
    for horizon,hold in WINDOWS.items():
        start=max(split,MIN_HISTORY[horizon]-1)
        if start+hold>=len(candles):
            results[horizon]={"status":"INSUFFICIENT_TEST_WINDOW","trades":0}
            continue
        trades=[]
        examined=0
        i=start
        while i+hold<len(candles):
            examined+=1
            # All indicators are causal and are sliced at the signal date.
            prefix=candles[:i+1]
            state,_=evaluate(prefix,{k:v[:i+1] for k,v in ind.items()}, {})[horizon]
            if state!="TECHNICAL_WATCH":
                i+=1
                continue
            entry=candles[i+1]
            exit_candle=candles[i+hold]
            trades.append((entry.open,exit_candle.close,[c.close for c in candles[i+1:i+hold+1]]))
            # No overlapping exposure within an instrument/horizon.
            i+=hold
        results[horizon]={"status":"REPLAY_OBSERVED" if trades else "NO_SIGNALS","trades":len(trades),
            "examined_signal_dates":examined,"holding_sessions":hold,"test_start":candles[start].date,
            "test_end":candles[-1].date,"cost_scenarios":[_metrics(trades,cost) for cost in COSTS] if trades else [],
            "small_sample":len(trades)<30,
            "gross_buy_hold_percent":round((candles[-1].close/candles[start+1].open-1)*100,4)}
    return {"status":"HISTORICAL_REPLAY_ONLY","methodology":VERSION,
            "history_count":len(candles),"as_of":candles[-1].date,"horizons":results,
            "notice":"Fixed technical rules, chronological holdout, next-session open and fixed-session close. Costs are illustrative; gross same-asset buy-and-hold and matched gross exposure are not market index benchmarks. Current registry selection and revised history can introduce bias. No validated forward performance or recommendation."}
