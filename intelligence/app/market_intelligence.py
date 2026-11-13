"""Integrated, bounded daily market intelligence. Deterministic observations only.

No full-exchange coverage, live feed, forecast, trade action or background polling.
"""
from datetime import date
from math import isfinite
from .risk_qualification import qualify

MAX_UNIVERSE=20
ALLOWED_ADJUSTMENTS={"RAW_UNADJUSTED","ADJUSTED"}

def analyze_market(instruments,load_candles,as_of=None,max_age_days=7):
    today=as_of or date.today()
    if not isinstance(instruments,list):
        raise ValueError("Expected instrument registry list")
    skipped={"INSUFFICIENT_HISTORY":0,"STALE_OR_FUTURE":0,"MIXED_OR_UNVERIFIED_ADJUSTMENT":0,
             "INVALID_CANDLES":0,"BACKEND_UNAVAILABLE":0}
    rows=[]
    for instrument in instruments[:MAX_UNIVERSE]:
        try:
            raw=load_candles(instrument["id"])
        except Exception:
            skipped["BACKEND_UNAVAILABLE"]+=1
            continue
        if not isinstance(raw,dict) or not isinstance(raw.get("candles"),list):
            skipped["INVALID_CANDLES"]+=1
            continue
        candles=raw["candles"]
        if len(candles)<50:
            skipped["INSUFFICIENT_HISTORY"]+=1
            continue
        adjustments={x.get("adjustment_status") for x in candles if isinstance(x,dict)}
        if len(adjustments)!=1 or not adjustments.issubset(ALLOWED_ADJUSTMENTS):
            skipped["MIXED_OR_UNVERIFIED_ADJUSTMENT"]+=1
            continue
        assessment=qualify(raw,as_of=today,max_age_days=max_age_days)
        if assessment["status"]!="OBSERVATIONS_READY":
            failures=assessment["failures"]
            category=("STALE_OR_FUTURE" if "STALE_OR_FUTURE_DATA" in failures else "INVALID_CANDLES")
            skipped[category]+=1
            continue
        try:
            last,previous=candles[-1],candles[-2]
            close,prev=float(last["close"]),float(previous["close"])
            volume=int(last["volume"])
            prior_volumes=[int(x["volume"]) for x in candles[-21:-1]]
            prior_high=max(float(x["high"]) for x in candles[-21:-1])
            prior_low=min(float(x["low"]) for x in candles[-21:-1])
            day_high,day_low=float(last["high"]),float(last["low"])
            day_open=float(last["open"])
            if prev<=0 or any(v<0 for v in prior_volumes) or not all(isfinite(v) for v in (prior_high,prior_low,day_high,day_low,day_open)):
                raise ValueError("Invalid market observations")
            avg_volume=sum(prior_volumes)/20
            relative_volume=round(volume/avg_volume,3) if avg_volume>0 else None
            change=round((close/prev-1)*100,3)
            momentum=round((close/float(candles[-21]["close"])-1)*100,3)
            flags=[]
            if relative_volume is not None and relative_volume>=2:
                flags.append("UNUSUAL_VOLUME_2X")
            if abs(change)>=5:
                flags.append("LARGE_DAILY_MOVE_5_PERCENT")
            if close>prior_high:
                flags.append("CLOSE_ABOVE_PRIOR_20D_HIGH")
            if close<prior_low:
                flags.append("CLOSE_BELOW_PRIOR_20D_LOW")
            # A same-day failed break is a *candidate*, not proof of manipulation.
            if day_high>prior_high and close<=prior_high:
                flags.append("FAILED_UPSIDE_BREAK_CANDIDATE")
            if day_low<prior_low and close>=prior_low:
                flags.append("FAILED_DOWNSIDE_BREAK_CANDIDATE")
            if day_high>day_low:
                upper_wick=(day_high-max(day_open,close))/(day_high-day_low)
                lower_wick=(min(day_open,close)-day_low)/(day_high-day_low)
                if upper_wick>=0.6:flags.append("LONG_UPPER_WICK")
                if lower_wick>=0.6:flags.append("LONG_LOWER_WICK")
            rows.append({"id":instrument["id"],"symbol":instrument["symbol"],
                "exchange":instrument["exchange"],"as_of":assessment["as_of"],
                "adjustment_status":next(iter(adjustments)),"close":round(close,4),
                "change_1d_percent":change,"momentum_20d_percent":momentum,
                "relative_volume_20":relative_volume,"rsi_14":assessment["observations"]["rsi_14"],
                "trend":assessment["observations"]["trend"],
                "atr_percent_of_close":assessment["observations"]["atr_percent_of_close"],
                "flags":flags+assessment["observations"]["warnings"]})
        except (KeyError,TypeError,ValueError,ZeroDivisionError,OverflowError):
            skipped["INVALID_CANDLES"]+=1
    def ordered(items,key,reverse=True):
        return sorted(items,key=lambda r:((-r[key] if reverse else r[key]),r["exchange"],r["symbol"]))[:5]
    gainers=ordered(rows,"change_1d_percent")
    losers=ordered(rows,"change_1d_percent",False)
    momentum=ordered(rows,"momentum_20d_percent")
    volume=sorted((r for r in rows if r["relative_volume_20"] is not None),
                  key=lambda r:(-r["relative_volume_20"],r["exchange"],r["symbol"]))[:5]
    anomalies=sorted((r for r in rows if r["flags"]),
                     key=lambda r:(-len(r["flags"]),r["exchange"],r["symbol"]))[:10]
    up=sum(r["change_1d_percent"]>0 for r in rows)
    down=sum(r["change_1d_percent"]<0 for r in rows)
    return {"status":"RESEARCH_ONLY","timeframe":"1d","as_of":today.isoformat(),
        "universe_size":min(len(instruments),MAX_UNIVERSE),"eligible_count":len(rows),
        "skipped":skipped,"breadth":{"advancing":up,"declining":down,"unchanged":len(rows)-up-down},
        "top_gainers":gainers,"top_losers":losers,"momentum_leaders":momentum,
        "volume_leaders":volume,"anomaly_watch":anomalies,
        "notice":"On-demand observations from at most 20 registry instruments, not exchange-wide rankings. Breakout/trap flags are heuristic candidates, not proof, predictions, alerts or trade recommendations."}
