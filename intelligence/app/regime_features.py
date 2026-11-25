"""Shared causal price-index features for current and historical regime research."""
from hashlib import sha256
from math import isfinite,log,sqrt
from statistics import pstdev

VERSION="NIFTY-TREND-VOLATILITY-1"
LOOKBACK=60
TREND_THRESHOLD=5.0
HIGH_VOL=25.0

def describe(dates,closes):
    if len(dates)!=LOOKBACK+1 or len(closes)!=len(dates) or dates!=sorted(set(dates)):
        return None
    try:
        values=[float(v) for v in closes]
        if any(not isfinite(v) or not 0<v<=1e9 for v in values):
            return None
        change=100*(values[-1]/values[0]-1)
        volatility=100*pstdev([log(b/a) for a,b in zip(values[-21:-1],values[-20:])])*sqrt(252)
        if not all(isfinite(v) for v in (change,volatility)):
            return None
        fingerprint=sha256(("\n".join(d+"|"+v.hex() for d,v in zip(dates,values))).encode()).hexdigest()
        return {"trend":"RISING" if change>=TREND_THRESHOLD else "FALLING" if change<=-TREND_THRESHOLD else "SIDEWAYS",
                "volatility_regime":"HIGH_HISTORICAL_VOLATILITY" if volatility>=HIGH_VOL else "BELOW_HIGH_THRESHOLD",
                "benchmark_change_60_percent":round(change,4),"volatility_20_annualized_percent":round(volatility,4),
                "benchmark_fingerprint":fingerprint}
    except (ValueError,TypeError,OverflowError,ZeroDivisionError):
        return None
