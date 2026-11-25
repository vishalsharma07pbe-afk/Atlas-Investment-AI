"""Causal daily price/volume diagnostics; no participant or trade attribution."""
from datetime import date
from math import isfinite
from statistics import median
from . import breakout_followthrough

DOWNSIDE=frozenset(("HIGH_VOLUME_DECLINE_REVIEW","HIGH_VOLUME_UPSIDE_REJECTION_REVIEW"))
UPSIDE=frozenset(("HIGH_VOLUME_ADVANCE_OBSERVATION","HIGH_VOLUME_DOWNSIDE_REJECTION_OBSERVATION"))
NOTICE=("Prior 20 available daily observations, not a full session-continuity audit. "
        "2x median volume, 2% close change and outer-quarter closing range are descriptive research heuristics, not validated signals. "
        "Price/volume cannot identify institutional dumping, accumulation, order flow or intent. Raw prices and share volume can be distorted by corporate actions; adjusted volume basis is unverified. Historical price-times-volume is not executable liquidity.")


def analyze(candles,*,calendar_verified=False):
    result={"status":"UNAVAILABLE","findings":[],"notice":NOTICE}
    if not calendar_verified or len(candles)<21:
        return result
    rows=candles[-21:]
    try:
        days=[date.fromisoformat(c.date) for c in rows]
        if (any(not 0<(b-a).days<=7 for a,b in zip(days,days[1:]))
            or {c.adjustment_status for c in rows} not in ({"RAW_UNADJUSTED"},{"ADJUSTED"})
            or any(type(c.volume) is not int or c.volume<=0 or
                not all(type(v) in (int,float) and isfinite(v) and v>0 for v in (c.open,c.high,c.low,c.close))
                or not c.low<=min(c.open,c.close)<=max(c.open,c.close)<=c.high for c in rows)):
            return result
        prior=rows[:-1]
        last=rows[-1]
        base=median(c.volume for c in prior)
        relative=last.volume/base
        change=100*(last.close/prior[-1].close-1)
        traded=median(c.close*c.volume for c in prior)
        upper=max(c.high for c in prior)
        lower=min(c.low for c in prior)
        position=(last.close-last.low)/(last.high-last.low) if last.high>last.low else None
        if not all(isfinite(v) for v in (relative,change,traded,upper,lower)):
            return result
        findings=[]
        if relative>=2 and position is not None:
            if change<=-2 and position<=.25:
                findings.append("HIGH_VOLUME_DECLINE_REVIEW")
            if last.high>upper and last.close<upper and position<=.25:
                findings.append("HIGH_VOLUME_UPSIDE_REJECTION_REVIEW")
            if change>=2 and position>=.75:
                findings.append("HIGH_VOLUME_ADVANCE_OBSERVATION")
            if last.low<lower and last.close>lower and position>=.75:
                findings.append("HIGH_VOLUME_DOWNSIDE_REJECTION_OBSERVATION")
        return {**result,"status":"OBSERVED_PRICE_VOLUME_ONLY","as_of":last.date,"adjustment_status":last.adjustment_status,
            "calendar_status":"LATEST_SESSION_MATCHED_ONLY","relative_volume":round(relative,4),"change_percent":round(change,4),
            "close_range_position":round(position,4) if position is not None else None,
            "prior_median_traded_value":round(traded,2),"prior_range_high":upper,"prior_range_low":lower,
            "findings":findings,
            "breakout_followthrough":breakout_followthrough.analyze(candles,calendar_verified=calendar_verified)}
    except (ValueError,TypeError,AttributeError,OverflowError,ZeroDivisionError):
        return result
