"""Causal recent range-break follow-through on adjusted completed daily observations."""
from datetime import date
from math import isfinite
from statistics import median

BASE=20
FOLLOW=3
BREAK_BUFFER=.005
REENTRY_BUFFER=.0025
NOTICE=("Recent close beyond the preceding 20 available observations by at least 0.5%; "
        "the original boundary stays frozen for up to three subsequent available observations. "
        "A close back through the boundary by at least 0.25% records re-entry, not proof of a bull/bear trap. "
        "Pending, held beyond boundary and inconclusive observations remain distinct. "
        "Volume relative to the prior median is descriptive; adjusted volume basis and full session continuity are unverified. "
        "No manipulation attribution, future reversal probability, execution or validated strategy.")

def analyze(candles,*,calendar_verified=False):
    result={"status":"UNAVAILABLE","events":[],"notice":NOTICE}
    if not calendar_verified or len(candles)<BASE+FOLLOW+1:
        return result
    rows=candles[-(BASE+FOLLOW+1):]
    try:
        dates=[date.fromisoformat(c.date) for c in rows]
        if (any(not 0<(b-a).days<=7 for a,b in zip(dates,dates[1:]))
            or any(c.adjustment_status!="ADJUSTED" or type(c.volume) is not int or c.volume<=0
                   or not all(type(v) in (int,float) and isfinite(v) and v>0 for v in (c.open,c.high,c.low,c.close))
                   or not c.low<=min(c.open,c.close)<=max(c.open,c.close)<=c.high for c in rows)):
            return result
        events=[]
        # Each episode uses only its own preceding observations. Never reset
        # the original threshold when the subsequent bars extend the range.
        for i in range(BASE,len(rows)):
            prior=rows[i-BASE:i]
            signal=rows[i]
            upper=max(c.high for c in prior)
            lower=min(c.low for c in prior)
            relative=signal.volume/median(c.volume for c in prior)
            if not isfinite(relative):
                continue
            direction=None
            if signal.close>=upper*(1+BREAK_BUFFER) and prior[-1].close<=upper:
                direction,boundary,sign="UPSIDE",upper,1
            elif signal.close<=lower*(1-BREAK_BUFFER) and prior[-1].close>=lower:
                direction,boundary,sign="DOWNSIDE",lower,-1
            if direction is None:
                continue
            subsequent=rows[i+1:i+1+FOLLOW]
            moves=[sign*(c.close/boundary-1) for c in subsequent]
            break_percent=100*(signal.close/boundary-1)
            if not all(isfinite(v) for v in [break_percent,*moves]):
                continue
            crossing=next((j for j,v in enumerate(moves) if v<=-REENTRY_BUFFER),None)
            if crossing is not None:
                status="REENTRY_OBSERVED"
            elif len(subsequent)<FOLLOW:
                status="PENDING_FOLLOWTHROUGH"
            elif all(v>=BREAK_BUFFER for v in moves):
                status="HELD_BEYOND_BOUNDARY"
            else:
                status="INCONCLUSIVE_FOLLOWTHROUGH"
            events.append({"direction":direction,"status":status,"signal_date":signal.date,
                "boundary":boundary,"signal_close":signal.close,"break_percent":round(break_percent,4),
                "relative_volume":round(relative,4),"volume_context":"HIGH_RELATIVE_VOLUME" if relative>=2 else "BELOW_HIGH_VOLUME_THRESHOLD",
                "followup_count":len(subsequent),"reentry_date":subsequent[crossing].date if crossing is not None else None})
        return {**result,"status":"OBSERVED_FOLLOWTHROUGH","as_of":rows[-1].date,
                "adjustment_status":"ADJUSTED","events":events}
    except (ValueError,TypeError,AttributeError,OverflowError,ZeroDivisionError):
        return result
