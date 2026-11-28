"""Frozen causal price-bracket research; no order, fill or profit prediction."""
from contextlib import closing
from datetime import date,timedelta
from math import isfinite
from statistics import mean,median
from zoneinfo import ZoneInfo
import json
import re
from . import price_structure
from .replay_evidence import full_manifest,exact_isin,corporate_action_status
from .corporate_action_normalization import reported_crossings

VERSION="BRACKET-SCENARIO-1"
COSTS=(15,30,60)
RATIO=2.
IST=ZoneInfo("Asia/Kolkata")
NOTICE=("Fixed historical support/resistance scenario, not a live entry, executable target or stop. "
        "Next regular session open observation only; entry must lie strictly inside bracket and meet illustrative 2:1 stressed geometry. An intervening boundary touch invalidates the bracket. "
        "Gap below lower level uses the observed open, gap above upper uses the upper reference; if both levels touched after an inside open, order is unknown and return withheld. "
        "Expiry uses final observed close. Costs and fills are hypothetical; taxes, spread, slippage and intraday liquidity not validated. "
        "No qualification, probability or recommendation promotion.")

def number(v):return type(v) in (int,float) and isfinite(v)
def ceiling(low,high,stress,bps):
    c=bps/10000
    return (high+RATIO*low*(1-stress/100))*(1-c)/((1+RATIO)*(1+c))

def _geometry(structure,horizon):
    if horizon not in price_structure.WINDOWS or structure.get("adjustment_status")!="ADJUSTED" or structure.get("scenario_status")!="ILLUSTRATIVE_HISTORICAL_GEOMETRY":return None
    s=structure.get("scenario") or {};stress=structure.get("risk_sensitivity") or {}
    close,low,high,gap=(s.get("reference_close"),s.get("lower_reference"),s.get("upper_reference"),stress.get("stress_gap_percent"))
    if not all(number(x) for x in (close,low,high,gap)) or not 0<low<close<high or not 2<=gap<100:return None
    try:
        a,b=structure["support"][0],structure["resistance"][0];day=structure["as_of"]
        if a["price"]!=low or b["price"]!=high or any(not date.fromisoformat(p["observed_on"])<date.fromisoformat(p["confirmed_on"])<=date.fromisoformat(day) for p in (a,b)):return None
    except (ValueError,TypeError,KeyError,IndexError):return None
    scenarios=[]
    for bps in COSTS:
        cap=ceiling(low,high,gap,bps)
        scenarios.append({"cost_bps_per_side":bps,"entry_ceiling":round(cap,6) if low<cap<high else None,
            "reference_meets_stress":low<close<=cap<high})
    return {"methodology":VERSION,"horizon":horizon,"as_of":day,"reference_close":close,"lower_reference":low,"upper_reference":high,
        "stress_gap_percent":gap,"ratio_assumption":RATIO,"entry_cases":scenarios,"support":a,"resistance":b,"notice":NOTICE}

def observe(raw,structure,horizon,expected_dates,today):
    g=_geometry(structure,horizon)
    if g is None:return None
    n=price_structure.WINDOWS[horizon]
    if len(raw)<n or len(expected_dates)<n:return None
    manifest=full_manifest(raw[-n:],today)
    if not manifest or tuple(manifest["observations"])!=tuple(expected_dates[-n:]) or manifest["last_date"]!=g["as_of"]:return None
    if float(raw[-1]["close"])!=g["reference_close"]:return None
    return {**g,"status":"STRICT_HISTORICAL_BRACKET","calendar_status":"STORED_SESSIONS_MATCHED","adjustment_status":"ADJUSTED",
        "first_date":manifest["first_date"],"history_fingerprint":manifest["digest"],"history_count":n,"source_code":raw[-1]["source_code"]}

def freeze(item,horizon,group,coverage,today):
    from .horizon_research import VERSION as TECH
    p=item.get("bracket_research")
    if not isinstance(p,dict) or not exact_isin(item.get("isin")) or item.get("adjustment_status")!="ADJUSTED" or item.get("security_state") in ("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED"):return None
    if group.get("methodology")!=TECH or group.get("status")!="TECHNICAL_WATCH_ONLY" or p.get("methodology")!=VERSION or p.get("status")!="STRICT_HISTORICAL_BRACKET" or p.get("horizon")!=horizon:return None
    try:
        if p["as_of"]!=item["as_of"] or not number(item.get("close")) or round(p["reference_close"],4)!=round(item["close"],4) or coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION" or coverage.get("expected_session")!=item["as_of"] or not 1<=(today-date.fromisoformat(p["as_of"])).days<=4:return None
        if p["history_count"]!=price_structure.WINDOWS[horizon] or p["calendar_status"]!="STORED_SESSIONS_MATCHED" or p["adjustment_status"]!="ADJUSTED" or not re.fullmatch(r"[a-f0-9]{64}",p["history_fingerprint"]):return None
        # Recompute from original causal geometry; do not trust a stored ceiling.
        g=_geometry(item.get("price_structure") or {},horizon)
        if g is None or any(p.get(k)!=v for k,v in g.items()):return None
        return p
    except (KeyError,ValueError,TypeError):return None

def simulate(p,bars,bps):
    """One next-open observation, no waiting for a more favorable later open."""
    if not bars or bps not in COSTS:return {"status":"EVIDENCE_GAP"}
    low,high,gap=(p.get(k) for k in ("lower_reference","upper_reference","stress_gap_percent"))
    if not all(number(v) for v in (low,high,gap)) or not 0<low<high or not 2<=gap<100:return {"status":"EVIDENCE_GAP"}
    try:
        rows=[]
        for r in bars:
            d=r["trade_date"];o,h,l,c=(float(r[k]) for k in ("open","high","low","close"))
            if not all(isfinite(v) and v>0 for v in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:return {"status":"EVIDENCE_GAP"}
            rows.append((d,o,h,l,c))
        entry=rows[0][1];cap=ceiling(low,high,gap,bps)
        if not low<entry<high:return {"status":"NO_ENTRY_OUTSIDE_BRACKET","observed_open":entry}
        if entry>cap:return {"status":"NO_ENTRY_STRESS_RATIO","observed_open":entry}
        cost=bps/10000
        def net(exit):return round(100*(exit*(1-cost)/(entry*(1+cost))-1),6)
        for d,o,h,l,c in rows:
            if o<=low:return {"status":"LOWER_GAP","entry_date":rows[0][0],"entry_open":entry,"exit_date":d,"exit_reference":o,"net_change_percent":net(o)}
            if o>=high:return {"status":"UPPER_GAP","entry_date":rows[0][0],"entry_open":entry,"exit_date":d,"exit_reference":high,"net_change_percent":net(high)}
            if l<=low and h>=high:return {"status":"AMBIGUOUS_BOTH_BOUNDARIES","entry_date":rows[0][0],"entry_open":entry,"exit_date":d,"lower_case_net_percent":net(low),"upper_case_net_percent":net(high)}
            if l<=low:return {"status":"LOWER_TOUCHED","entry_date":rows[0][0],"entry_open":entry,"exit_date":d,"exit_reference":low,"net_change_percent":net(low)}
            if h>=high:return {"status":"UPPER_TOUCHED","entry_date":rows[0][0],"entry_open":entry,"exit_date":d,"exit_reference":high,"net_change_percent":net(high)}
        return {"status":"EXPIRED_CLOSE","entry_date":rows[0][0],"entry_open":entry,"exit_date":rows[-1][0],"exit_reference":rows[-1][-1],"net_change_percent":net(rows[-1][-1])}
    except (KeyError,TypeError,ValueError,OverflowError):return {"status":"EVIDENCE_GAP"}

def evaluate_frozen(p,instrument,raw,expected,calendar,today,action_report,instant):
    # Verify original source capture and the entire bridge from its first
    # observation to maturity; do not compare levels across a later split.
    try:
        first=date.fromisoformat(p["first_date"]);signal=date.fromisoformat(p["as_of"]);end=expected[-1]
        if not first<signal<expected[0]<=end<today or calendar.get("through")!=(today-timedelta(days=1)).isoformat() or calendar.get("exchange")!=instrument["exchange"]:return None
        states={}
        for r in calendar["days"]:
            d=date.fromisoformat(r["trade_date"])
            if d in states:return None
            states[d]=r["state"]
        dates=[]
        for i in range((end-first).days+1):
            d=first+timedelta(days=i);state=states.get(d)
            if state=="REGULAR":dates.append(d.isoformat())
            elif state!="CLOSED":return None
        bridge=[r for r in raw if first<=date.fromisoformat(r["trade_date"])<=end]
        bridge.sort(key=lambda r:r["trade_date"])
        m=full_manifest(bridge,today)
        if not m or list(m["observations"])!=dates or bridge[-1]["source_code"]!=p["source_code"]:return None
        original=full_manifest([r for r in bridge if r["trade_date"]<=p["as_of"]],today)
        if not original or len(original["observations"])!=p["history_count"] or original["digest"]!=p["history_fingerprint"]:return None
        if corporate_action_status(instrument,m,require_scope=True,today=today)!="NO_RECORDED_CROSSING_ACTION":return None
        if instant is not None and reported_crossings(action_report,instrument["isin"],first,end,instant):return None
        future=[r for r in bridge if date.fromisoformat(r["trade_date"]) in set(expected)]
        if [r["trade_date"] for r in future]!=[d.isoformat() for d in expected]:return None
        # A bracket already touched between signal and first post-publication
        # open is not a fresh scenario, even when the subsequent open returns
        # inside it. Do not retrospectively enter on an earlier bar.
        intervening=[r for r in bridge if signal<date.fromisoformat(r["trade_date"])<expected[0]]
        invalidated=any(float(r["low"])<=p["lower_reference"] or float(r["high"])>=p["upper_reference"] for r in intervening)
        return {"methodology":VERSION,"status":"OBSERVED_BRACKET_CASES","history_fingerprint":p["history_fingerprint"],
            "cases":[{"cost_bps_per_side":bps,**({"status":"NO_ENTRY_INTERVENING_BOUNDARY_TOUCH"} if invalidated else simulate(p,future,bps))} for bps in COSTS],"notice":NOTICE}
    except (KeyError,TypeError,ValueError,OverflowError,AttributeError):return None

def summarize_cases(cases,denominator):
    from collections import Counter
    counts=Counter(r["status"] for r in cases)
    values=[r["net_change_percent"] for r in cases if number(r.get("net_change_percent"))]
    return {"counts":dict(counts),"observed_cases":len(cases),"eligible_cases":denominator,"return_cases":len(values),
        "coverage_percent":round(100*len(cases)/denominator,2) if denominator else 0,
        "mean_net_change_percent":round(mean(values),4) if values else None,"median_net_change_percent":round(median(values),4) if values else None,
        "worst_net_change_percent":min(values) if values else None}

def replay(payload,today,positions):
    """Same already selected nonoverlapping historical horizon signal cohort."""
    from .strategy_validation import _history,WINDOWS
    from .technical import compute
    candles=_history(payload,today);ind=compute(candles)
    index={c.date:i for i,c in enumerate(candles)}
    out={}
    for horizon,signals in positions.items():
        if horizon not in WINDOWS:continue
        cases={bps:[] for bps in COSTS};eligible=0
        for signal,_ in signals:
            i=index.get(signal)
            if i is None or i+WINDOWS[horizon]>=len(candles):continue
            eligible+=1
            s=price_structure.analyze(candles[:i+1],{k:v[:i+1] for k,v in ind.items()},horizon,calendar_verified=True)
            p=_geometry(s,horizon)
            if p is None:continue
            future=[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close} for c in candles[i+1:i+WINDOWS[horizon]+1]]
            for bps in COSTS:cases[bps].append(simulate(p,future,bps))
        out[horizon]={"methodology":VERSION,"status":"DESCRIPTIVE_MATCHED_SIGNAL_COHORT","signal_count":eligible,
            "cost_scenarios":[{"cost_bps_per_side":bps,**summarize_cases(cases[bps],eligible)} for bps in COSTS],
            "notice":NOTICE+" Same historical fixed-hold signal selection; not a separately optimized strategy."}
    return out

def prospective(connect,instant):
    from . import research_reliability as rel
    today=instant.astimezone(IST).date();out={}
    with closing(connect()) as db:
        rel._table(db)
        for horizon in rel.HORIZONS:
            rows=db.execute("""SELECT * FROM watch_outcomes WHERE horizon=? AND published_at>=? ORDER BY published_at,instrument_id,observed_date LIMIT 5001""",(horizon,(instant-timedelta(days=366)).isoformat())).fetchall()
            last={};selected=legacy=overlap=immature=0;cases={bps:[] for bps in COSTS}
            for row in rows[:5000]:
                try:
                    e=json.loads(row["evidence"]);isin=e.get("isin");published=rel._stamp(row["published_at"]);maturity=date.fromisoformat(row["maturity_date"])
                    if not exact_isin(isin) or e.get("methodology")!=rel.VERSION or e.get("adjustment_status")!="ADJUSTED" or not today-timedelta(days=365)<=published<=today or not 1<=(published-date.fromisoformat(row["observed_date"])).days<=4 or maturity!=published+timedelta(days=rel.HORIZONS[horizon]):continue
                    if today<=maturity+timedelta(days=7):immature+=1;continue
                    if isin in last and published<=last[isin]:overlap+=1;continue
                    last[isin]=maturity+timedelta(days=7)
                    p=e.get("bracket_research") or {}
                    if p.get("methodology")!=VERSION or p.get("horizon")!=horizon:legacy+=1;continue
                    selected+=1
                    if rel._outcome(row,published,maturity,today) is None:continue
                    result=(json.loads(row["outcome"]).get("bracket_research") or {})
                    if result.get("methodology")!=VERSION or result.get("history_fingerprint")!=p.get("history_fingerprint") or result.get("status")!="OBSERVED_BRACKET_CASES":continue
                    for bps in COSTS:
                        matches=[r for r in result.get("cases",[]) if r.get("cost_bps_per_side")==bps]
                        if len(matches)==1 and matches[0].get("status")!="EVIDENCE_GAP":cases[bps].append(matches[0])
                except (KeyError,ValueError,TypeError,OverflowError):continue
            out[horizon]={"status":"DESCRIPTIVE_CASES_AVAILABLE" if cases[30] and len(rows)<=5000 else "AWAITING_EVIDENCE",
                "selected_mature":selected,"legacy_uninstrumented":legacy,"overlap_excluded":overlap,"immature":immature,"truncated":len(rows)>5000,
                "cost_scenarios":[{"cost_bps_per_side":bps,**summarize_cases(cases[bps],selected)} for bps in COSTS],"notice":NOTICE}
    return {"methodology":VERSION,"horizons":out,"notice":NOTICE}
