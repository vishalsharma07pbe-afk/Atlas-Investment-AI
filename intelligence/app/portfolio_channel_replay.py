"""Shared cash Turtle-style research replay on exact matched audited histories.

Current registry sample only. Close-confirmed next-open entries/exits/adds;
not canonical intraday Turtle fills, not historical constituent membership.
"""
from math import isfinite,sqrt
from statistics import mean,pstdev
from .professional_strategies import channel_risk_inputs
from .technical import Candle
from .replay_evidence import exact_isin

VERSION="SHARED-CASH-CHANNEL-1"
def num(v,lo,hi):return type(v) in (int,float) and isfinite(v) and lo<=v<=hi

def pack(candles):
    # Local cache only; never expose individual histories through public response.
    return [[c.date,c.open,c.high,c.low,c.close,c.volume] for c in candles[-500:]]

def unpack(raw):
    from datetime import date
    if not isinstance(raw,list) or not 316<=len(raw)<=500:return None
    try:
        out=[];prev=None
        for d,o,h,l,c,v in raw:
            day=date.fromisoformat(d)
            if prev is not None and day<=prev:return None
            if not all(num(x,.00001,1e9) for x in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h or not num(v,0,1e14):return None
            out.append(Candle(d,o,h,l,c,v,"ADJUSTED"));prev=day
        return out
    except (ValueError,TypeError,OverflowError):return None

def simulate(histories,*,capital=1000000,bps=30):
    if not num(capital,10000,1e12) or not num(bps,0,1000):raise ValueError("PARAMETERS")
    if not isinstance(histories,dict) or not 2<=len(histories)<=12:return None
    names=sorted(histories)
    if any(not exact_isin(k) for k in names):return None
    dates=[c.date for c in histories[names[0]]]
    if len(dates)<316 or any([c.date for c in histories[k]]!=dates for k in names):return None
    start=max(253,int(len(dates)*.6));cost=bps/10000
    cash=float(capital);held={};pending={};completed=[];path=[cash];adds=0;max_units=0
    from .multi_strategy import price_features,price_lanes
    def decisions(i):
        result={}
        for k in names:
            c=histories[k][i];window=histories[k][i-252:i+1];p=held.get(k)
            if p:
                channel=min(x.low for x in window[-21:-1])
                if c.close<=max(channel,p["stop"]):result[k]=("EXIT",None)
                elif p["units"]<4 and c.close>=p["last_add"]+.5*p["n"]:result[k]=("ADD",p["n"])
            else:
                f=price_features(window,[x.date for x in window])
                if f and "TURTLE_LONG_BREAKOUT" in price_lanes(f):
                    a=channel_risk_inputs(window)
                    if a and a["n"]/c.close<=.05:result[k]=("ENTRY",a["n"])
        return result
    pending=decisions(start-1)
    for i in range(start,len(dates)):
        # Exits first, then deterministic ISIN order; same pool of cash.
        for k in names:
            p=held.get(k);action=pending.get(k,(None,None))[0]
            if p and action=="EXIT":
                proceeds=p["shares"]*histories[k][i].open*(1-cost)
                cash+=proceeds;completed.append(proceeds/p["basis"]-1);del held[k]
        for k in names:
            action,n=pending.get(k,(None,None));p=held.get(k)
            if action not in ("ENTRY","ADD") or (action=="ENTRY" and p) or (action=="ADD" and not p):continue
            o=histories[k][i].open;price=o*(1+cost)
            equity=cash+sum(v["shares"]*histories[j][i].open for j,v in held.items())
            if equity<=0 or o<=2*n:continue
            # Conservative 0.5% initial 2N loss per unit, 4% portfolio stop
            # risk, 20% per company, at most 6 companies and 4 units/company.
            if not p and len(held)>=6:continue
            old_shares=p["shares"] if p else 0
            stop=max(p["stop"] if p else 0,o-2*n)
            other_risk=sum(v["shares"]*max(0,histories[j][i].open-v["stop"]) for j,v in held.items() if j!=k)
            existing_risk=old_shares*max(0,o-stop)
            unit_risk=max(2*n,price-stop)
            shares=int(min(cash/price,max(0,equity*.2-old_shares*o)/price,
                equity*.005/unit_risk,max(0,equity*.04-other_risk-existing_risk)/unit_risk))
            if shares<=0:continue
            cash-=shares*price
            if p:
                p.update(shares=old_shares+shares,units=p["units"]+1,last_add=o,stop=stop,basis=p["basis"]+shares*price);adds+=1
            else:held[k]={"shares":shares,"units":1,"n":n,"last_add":o,"stop":stop,"basis":shares*price}
        max_units=max(max_units,sum(v["units"] for v in held.values()))
        path.append(cash+sum(v["shares"]*histories[k][i].close for k,v in held.items()))
        pending=decisions(i)
    changes=[b/a-1 for a,b in zip(path,path[1:]) if a>0];peak=path[0];dd=0
    for x in path:peak=max(peak,x);dd=min(dd,x/peak-1)
    sd=pstdev(changes) if changes else 0;down=sqrt(mean([min(0,x)**2 for x in changes])) if changes else 0
    gain=sum(x for x in completed if x>0);loss=-sum(x for x in completed if x<0)
    return {"methodology":VERSION,"status":"DESCRIPTIVE_SHARED_CASH_REPLAY","companies":len(names),
        "start":dates[start],"end":dates[-1],"cost_bps_per_side":bps,"completed_positions":len(completed),"pyramid_adds":adds,
        "maximum_open_units":max_units,"open_positions":len(held),"net_marked_return_percent":round(100*(path[-1]/capital-1),6),
        "max_drawdown_percent":round(100*dd,6),"annualized_sharpe_rf_zero":round(mean(changes)/sd*sqrt(252),6) if sd else None,
        "annualized_sortino_rf_zero":round(mean(changes)/down*sqrt(252),6) if down else None,
        "win_rate_percent":round(100*sum(x>0 for x in completed)/len(completed),6) if completed else None,
        "position_return_profit_factor":round(gain/loss,6) if loss else None,"qualified":False,
        "notice":"Current-registry matched sample only; shared capital, close-confirmed next-open fills, illustrative caps/costs, no point-in-time universe or total-return benchmark. Open positions marked, not liquidated."}

def from_cache(payloads,today):
    from datetime import date
    from collections import defaultdict
    cohorts=defaultdict(dict)
    for p in payloads:
        isin=p.get("isin");r=p.get("_portfolio_channel_history")
        if not exact_isin(isin) or not isinstance(r,list):continue
        c=unpack(r)
        if not c:continue
        if not 1<=(today-date.fromisoformat(c[-1].date)).days<=5:continue
        key=tuple(x.date for x in c)
        cohorts[key].setdefault(isin,c)
    if not cohorts:return None
    key=max(cohorts,key=lambda k:(len(cohorts[k]),k[-1],len(k),k))
    cohort=cohorts[key]
    if len(cohort)<2:return None
    # deterministic selection, not based on later returns.
    return simulate({k:cohort[k] for k in sorted(cohort)[:12]})
