"""Strict evidence-based research qualification, never a trading signal."""
from datetime import date
from math import isfinite

def qualify(raw, as_of=None, max_age_days=7):
    today=as_of or date.today()
    candles=raw.get("candles",[])
    failures=[]
    if len(candles)<50:
        failures.append("INSUFFICIENT_50_DAY_HISTORY")
    if not candles:
        return {"status":"BLOCKED","failures":failures or ["NO_CANDLES"],
                "observations":{},"notice":"Research eligibility only; not a trade recommendation."}
    try:
        dates=[date.fromisoformat(x["trade_date"]) for x in candles]
        if any(a>=b for a,b in zip(dates,dates[1:])):
            failures.append("INVALID_DATE_ORDER")
        age=(today-dates[-1]).days
        if age<0 or age>max_age_days:
            failures.append("STALE_OR_FUTURE_DATA")
        adjustments={x["adjustment_status"] for x in candles}
        if len(adjustments)!=1:
            failures.append("MIXED_ADJUSTMENT_STATUS")
        for x in candles:
            o,h,l,c=(float(x[k]) for k in ("open","high","low","close"))
            v=int(x["volume"])
            if not all(isfinite(n) for n in (o,h,l,c)) or l<=0 or l>min(o,c) or h<max(o,c) or v<0:
                failures.append("INVALID_OHLCV")
                break
        if failures:
            return {"status":"BLOCKED","failures":sorted(set(failures)),"observations":{},
                    "as_of":dates[-1].isoformat(),"notice":"Failed evidence gates; no strategy qualification."}
        from .technical import Candle,compute
        rows=[Candle(x["trade_date"],float(x["open"]),float(x["high"]),float(x["low"]),
                     float(x["close"]),int(x["volume"]),x["adjustment_status"]) for x in candles]
        indicators=compute(rows)
        latest={key:(values[-1] if values else None) for key,values in indicators.items()}
        required=("sma_20","sma_50","rsi_14","atr_14","relative_volume_20")
        if any(latest.get(key) is None or not isfinite(latest[key]) for key in required):
            failures.append("MISSING_REQUIRED_INDICATORS")
        if failures:
            return {"status":"BLOCKED","failures":failures,"observations":{},
                    "as_of":dates[-1].isoformat(),"notice":"Incomplete indicators; no strategy qualification."}
        close=rows[-1].close
        trend="ABOVE_20_AND_50_SMA" if close>latest["sma_20"] and close>latest["sma_50"] else (
            "BELOW_20_AND_50_SMA" if close<latest["sma_20"] and close<latest["sma_50"] else "MIXED")
        volatility_pct=100*latest["atr_14"]/close
        warnings=[]
        if latest["rsi_14"]>=70:warnings.append("RSI_OVERBOUGHT_ZONE")
        if latest["rsi_14"]<=30:warnings.append("RSI_OVERSOLD_ZONE")
        if volatility_pct>=5:warnings.append("HIGH_ATR_RELATIVE_TO_PRICE")
        if latest["relative_volume_20"]<0.5:warnings.append("LOW_RELATIVE_VOLUME")
        return {"status":"OBSERVATIONS_READY","failures":[],"as_of":dates[-1].isoformat(),
                "observations":{"trend":trend,"rsi_14":round(latest["rsi_14"],2),
                    "atr_percent_of_close":round(volatility_pct,2),
                    "relative_volume_20":round(latest["relative_volume_20"],2),
                    "warnings":warnings},
                "notice":"Passed historical data-quality gates only. No liquidity, fundamentals, event, institutional-flow or execution verification. No BUY/SELL, price target or stop-loss."}
    except (KeyError,ValueError,TypeError,OverflowError,ZeroDivisionError):
        return {"status":"BLOCKED","failures":["INVALID_DATA_FORMAT"],"observations":{},
                "notice":"Invalid market data; no strategy qualification."}
