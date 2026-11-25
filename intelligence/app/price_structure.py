"""Causal price structure on completed daily history; no trade instructions.

The scenario uses historical reference levels, not predicted targets or
executable stops. No scenario when actual overhead resistance is absent.
"""
from datetime import date, timedelta
from math import isfinite

WINDOWS={"SWING":60,"SHORT_TERM":120,"LONG_TERM":200}
COST_BPS=30


def _finite(x):
    return type(x) in (int,float) and isfinite(x)


def _valid(candles):
    try:
        dates=[date.fromisoformat(c.date) for c in candles]
        return (len(candles)>=21 and all(0<(b-a).days<=7 for a,b in zip(dates,dates[1:]))
                and {c.adjustment_status for c in candles} in ({"ADJUSTED"},{"RAW_UNADJUSTED"})
                and all(all(_finite(v) and v>0 for v in (c.open,c.high,c.low,c.close))
                        and c.low<=min(c.open,c.close)<=max(c.open,c.close)<=c.high
                        and type(c.volume) is int and c.volume>=0 for c in candles))
    except (TypeError,ValueError,AttributeError):
        return False


def _pivots(rows,kind):
    # Require a strict local extremum against two completed bars on either side.
    # Plateaus do not count as multiple independently confirmed touches.
    field="low" if kind=="support" else "high"
    found=[]
    for i in range(2,len(rows)-2):
        value=getattr(rows[i],field)
        neighbors=[getattr(rows[j],field) for j in (i-2,i-1,i+1,i+2)]
        if (all(value<x for x in neighbors) if kind=="support" else all(value>x for x in neighbors)):
            found.append({"price":value,"observed_on":rows[i].date,"confirmed_on":rows[i+2].date})
    return found


def _weekly(rows):
    # Exclude the latest observed ISO week. These are aggregates of available
    # daily observations, not exchange-calendar-verified complete weekly bars.
    groups={}
    for c in rows:
        day=date.fromisoformat(c.date)
        monday=day-timedelta(days=day.weekday())
        groups.setdefault(monday,[]).append(c)
    weeks=list(groups.items())[:-1]
    if len(weeks)<10:
        return {"status":"INSUFFICIENT_WEEKLY_OBSERVATIONS"}
    tail=weeks[-20:]
    if any((b[0]-a[0]).days!=7 for a,b in zip(tail,tail[1:])):
        return {"status":"WEEKLY_GAP"}
    closes=[bars[-1].close for _,bars in tail]
    last=closes[-1]
    avg10=sum(closes[-10:])/10
    avg20=sum(closes[-20:])/20 if len(closes)>=20 else None
    return {"status":"OBSERVED_WEEK_AGGREGATES","last_observed_date":tail[-1][1][-1].date,
            "week_count":len(tail),"close":round(last,4),"sma_10":round(avg10,4),
            "sma_20":round(avg20,4) if avg20 is not None else None,
            "trend":"ABOVE_BOTH" if avg20 is not None and last>avg10 and last>avg20 else
                    "BELOW_BOTH" if avg20 is not None and last<avg10 and last<avg20 else "MIXED_OR_PARTIAL"}


def analyze(candles,indicators,horizon,calendar_verified=False):
    result={"methodology":"PRICE-STRUCTURE-1","status":"UNAVAILABLE","support":[],"resistance":[],
            "scenario":None,"scenario_status":"INVALID_OR_INSUFFICIENT_HISTORY",
            "notice":"Historical reference levels and illustrative geometry only. Not a target, stop order, probability or validated strategy. Gaps and costs can exceed illustrated losses."}
    if horizon not in WINDOWS or not _valid(candles):
        return result
    close=candles[-1].close
    window=WINDOWS[horizon]
    rows=candles[-window:]
    supports=sorted((p for p in _pivots(rows,"support") if p["price"]<close),
                    key=lambda p:(-p["price"],p["observed_on"]))
    resistances=sorted((p for p in _pivots(rows,"resistance") if p["price"]>close),
                       key=lambda p:(p["price"],p["observed_on"]))
    def unique(pivots):
        chosen=[]
        for p in pivots:
            if not any(abs(p["price"]-q["price"])/q["price"]<.005 for q in chosen):
                chosen.append(p)
            if len(chosen)==3:
                break
        return chosen
    support,resistance=unique(supports),unique(resistances)
    keys=("rsi_14","adx_14","macd_histogram","ema_20","ema_50","bollinger_upper_20",
          "bollinger_lower_20","historical_volatility_20","relative_volume_20")
    observed={}
    for key in keys:
        values=indicators.get(key,[])
        if values and _finite(values[-1]):
            observed[key]=round(values[-1],6)
    result.update(status="HISTORICAL_STRUCTURE",as_of=candles[-1].date,reference_close=close,
                  lookback_count=len(rows),adjustment_status=candles[-1].adjustment_status,
                  calendar_status="LATEST_SESSION_VERIFIED" if calendar_verified else "UNVERIFIED",
                  support=support,resistance=resistance,indicators=observed,weekly=_weekly(candles))
    if not calendar_verified:
        result["scenario_status"]="CALENDAR_UNVERIFIED"
    elif candles[-1].adjustment_status!="ADJUSTED":
        result["scenario_status"]="ADJUSTED_HISTORY_REQUIRED"
    elif not support or not resistance:
        result["scenario_status"]="BRACKETING_CONFIRMED_LEVELS_REQUIRED"
    else:
        low,high=support[0]["price"],resistance[0]["price"]
        cost=COST_BPS/10000
        # Hypothetical purchase at the dated reference close, sale at either
        # observed boundary, with the same illustrative cost per side.
        debit=close*(1+cost)
        downside=(debit-low*(1-cost))/debit
        upside=(high*(1-cost)-debit)/debit
        if downside>0 and upside>0 and all(_finite(v) for v in (downside,upside,upside/downside)):
            result["scenario_status"]="ILLUSTRATIVE_HISTORICAL_GEOMETRY"
            result["scenario"]={"reference_close":close,"lower_reference":low,"upper_reference":high,
                                "cost_bps_per_side":COST_BPS,"downside_percent":round(100*downside,4),
                                "upside_percent":round(100*upside,4),
                                "reward_to_risk":round(upside/downside,4)}
        else:
            result["scenario_status"]="NONPOSITIVE_COST_ADJUSTED_UPSIDE"
    return result
