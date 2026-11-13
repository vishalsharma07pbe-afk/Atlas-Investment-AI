"""Explainable candle/chart patterns using only data available at detection time."""
from .technical import Candle

def detect(c:list[Candle], indicators:dict)->list[dict]:
    out=[]
    def add(i,t,refs,why,confirmed,invalidation):out.append({"pattern_type":t,"detection_timestamp":c[i].date,"supporting_candles":[c[j].date for j in refs],"explanation":why,"confirmation_status":"CONFIRMED" if confirmed else "UNCONFIRMED","invalidation_conditions":invalidation})
    for i,x in enumerate(c):
        span=x.high-x.low;body=abs(x.close-x.open);upper=x.high-max(x.open,x.close);lower=min(x.open,x.close)-x.low
        if span>0 and body/span<=.1:add(i,"DOJI",[i],"Real body is at most 10% of the daily range.",False,"A directional close beyond this candle's range.")
        if span>0 and lower>=2*max(body,span*.02) and upper<=max(body,span*.15):add(i,"HAMMER",[i],"Lower wick is at least twice the real body with a small upper wick.",False,"Confirmation requires a later completed close above the hammer high.")
        if span>0 and upper>=2*max(body,span*.02) and lower<=max(body,span*.15):add(i,"SHOOTING_STAR",[i],"Upper wick is at least twice the real body with a small lower wick.",False,"Confirmation requires a later completed close below the shooting-star low.")
        if i:
            p=c[i-1]
            if p.close<p.open and x.close>x.open and x.open<=p.close and x.close>=p.open:add(i,"BULLISH_ENGULFING",[i-1,i],"Bullish body fully engulfs the preceding bearish body.",False,"Close below the two-candle low.")
            if p.close>p.open and x.close<x.open and x.open>=p.close and x.close<=p.open:add(i,"BEARISH_ENGULFING",[i-1,i],"Bearish body fully engulfs the preceding bullish body.",False,"Close above the two-candle high.")
        if i>=2:
            a,b=c[i-2],c[i-1]
            if a.close<a.open and abs(b.close-b.open)<abs(a.close-a.open)*.4 and x.close>x.open and x.close>(a.open+a.close)/2:add(i,"MORNING_STAR",[i-2,i-1,i],"Bearish candle, small indecision body, then bullish recovery above the first midpoint.",False,"Close below the three-candle low.")
            if a.close>a.open and abs(b.close-b.open)<abs(a.close-a.open)*.4 and x.close<x.open and x.close<(a.open+a.close)/2:add(i,"EVENING_STAR",[i-2,i-1,i],"Bullish candle, small indecision body, then bearish close below the first midpoint.",False,"Close above the three-candle high.")
    if len(c)>=20:
        i=len(c)-1;x=c[i];prior=c[max(0,i-20):i];hi=max(p.high for p in prior);lo=min(p.low for p in prior);rv=indicators.get("relative_volume_20",[None]*len(c))[i]
        if x.close>hi:add(i,"VOLUME_SUPPORTED_BREAKOUT" if rv and rv>=1.5 else "BREAKOUT",list(range(max(0,i-3),i+1)),f"Close exceeded the prior 20-session high; relative volume is {rv:.2f}." if rv else "Close exceeded the prior 20-session high; volume confirmation unavailable.",bool(rv and rv>=1.5),"Close back below the prior range high.")
        if x.close<lo:add(i,"BREAKDOWN",list(range(max(0,i-3),i+1)),"Close fell below the prior 20-session low.",False,"Close back above the prior range low.")
        if x.high>hi and x.close<hi:add(i,"FALSE_BREAKOUT",list(range(max(0,i-2),i+1)),"Price traded above the prior range but closed back inside it.",True,"Later close above the failed-break level.")
    # Deterministic approximate multi-swing patterns; intentionally unconfirmed until neckline/range break.
    extrema=[i for i in range(2,len(c)-2) if c[i].high==max(x.high for x in c[i-2:i+3])]
    lows=[i for i in range(2,len(c)-2) if c[i].low==min(x.low for x in c[i-2:i+3])]
    if len(extrema)>=2:
        a,b=extrema[-2:]
        if b-a>=5 and abs(c[a].high-c[b].high)/c[a].high<=.03:add(b,"DOUBLE_TOP",[a,b],"Two swing highs are within 3%, separated by at least five sessions.",False,"Confirmation requires a later neckline close; new high invalidates.")
    if len(lows)>=2:
        a,b=lows[-2:]
        if b-a>=5 and abs(c[a].low-c[b].low)/c[a].low<=.03:add(b,"DOUBLE_BOTTOM",[a,b],"Two swing lows are within 3%, separated by at least five sessions.",False,"Confirmation requires a later neckline close; new low invalidates.")
    if len(extrema)>=3:
        a,b,d=extrema[-3:]
        if c[b].high>c[a].high*1.03 and abs(c[a].high-c[d].high)/c[a].high<=.05:add(d,"HEAD_AND_SHOULDERS",[a,b,d],"Middle swing high exceeds two shoulders whose highs are within 5%.",False,"Confirmation requires a neckline break; close above head invalidates.")
    if len(c)>=30:
        w=c[-30:];early=max(x.high for x in w[:10])-min(x.low for x in w[:10]);late=max(x.high for x in w[-10:])-min(x.low for x in w[-10:])
        if late<early*.65:add(len(c)-1,"TRIANGLE",list(range(len(c)-5,len(c))),"Recent 10-session range contracted below 65% of the earlier range.",False,"Confirmed only by a completed close outside the contracting range.")
    return out
