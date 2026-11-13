"""Deterministic daily SMA crossover backtest; no execution or predictive claims."""
from datetime import date
from math import isfinite
from .technical import sma

def backtest(raw, fast=10, slow=30, fee_bps=10, slippage_bps=5):
    if not 2 <= fast < slow <= 200:
        raise ValueError("Require 2 <= fast < slow <= 200")
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Invalid fee/slippage assumption")
    candles=raw["candles"]
    if len(candles)<slow+2:
        return {"status":"INSUFFICIENT_HISTORY","required_candles":slow+2,"observed_candles":len(candles),"trades":[]}
    dates=[date.fromisoformat(x["trade_date"]) for x in candles]
    if any(a>=b for a,b in zip(dates,dates[1:])):
        raise ValueError("Candles must have strictly increasing dates")
    if len({x["adjustment_status"] for x in candles})!=1:
        raise ValueError("Mixed adjustment statuses are not comparable")
    closes=[float(x["close"]) for x in candles]
    opens=[float(x["open"]) for x in candles]
    for x,o,c in zip(candles,opens,closes):
        h=float(x["high"]);l=float(x["low"])
        if not all(map(isfinite,(o,c,h,l))) or l<=0 or l>min(o,c) or h<max(o,c) or int(x["volume"])<0:
            raise ValueError("Invalid OHLCV data")
    short=sma(closes,fast);long=sma(closes,slow)
    equity=1.0;shares=0.0;entry_cost=0.0;entry_date=None;trades=[]
    curve=[{"date":dates[0].isoformat(),"equity":equity}]
    cost=(fee_bps+slippage_bps)/10000
    for i in range(1,len(candles)):
        # Yesterday's completed close determines today's open action.
        if i>=slow+1:
            cross_up=short[i-2]<=long[i-2] and short[i-1]>long[i-1]
            cross_down=short[i-2]>=long[i-2] and short[i-1]<long[i-1]
            if shares==0 and cross_up:
                entry_cost=equity
                shares=equity*(1-cost)/opens[i]
                equity=0
                entry_date=dates[i].isoformat()
            elif shares>0 and cross_down:
                equity=shares*opens[i]*(1-cost)
                trades.append({"entry_date":entry_date,"exit_date":dates[i].isoformat(),
                    "return_percent":round((equity/entry_cost-1)*100,4)})
                shares=0
        curve.append({"date":dates[i].isoformat(),"equity":equity+shares*closes[i]})
    final=curve[-1]["equity"]
    peak=curve[0]["equity"];drawdown=0.0
    for point in curve:
        peak=max(peak,point["equity"])
        drawdown=min(drawdown,point["equity"]/peak-1)
    benchmark=closes[-1]/closes[0]
    return {"status":"HISTORICAL_SIMULATION_ONLY",
        "parameters":{"fast_sma":fast,"slow_sma":slow,"fee_bps":fee_bps,"slippage_bps":slippage_bps},
        "as_of":dates[-1].isoformat(),"candle_count":len(candles),
        "strategy_total_return_percent":round((final-1)*100,3),
        "buy_hold_return_percent":round((benchmark-1)*100,3),
        "max_drawdown_percent":round(drawdown*100,3),
        "closed_trade_count":len(trades),"open_position_at_end":shares>0,
        "trades":trades,"equity_curve":curve,
        "notice":"Long-only SMA crossover, signals on completed daily close, fills at next daily open with assumed costs. No dividends, taxes, financing, liquidity, survivorship or corporate-action correction; not predictive or investment advice."}
