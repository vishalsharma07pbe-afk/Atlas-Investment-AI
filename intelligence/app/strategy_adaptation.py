"""Conservative prospective regime-aware strategy priority.

Only frozen publication-time regime, verified outcome and paired price index.
Two predeclared nonoverlapping outcome windows; no fitted coefficients, no
historical backfill, no qualification. Missing evidence retains static priority.
"""
from contextlib import closing
from datetime import date,timedelta
from collections import defaultdict
from statistics import median
from zoneinfo import ZoneInfo
import json
from . import watch_outcomes as w,research_reliability as rel
from .replay_evidence import exact_isin

VERSION="PROSPECTIVE-REGIME-PRIORITY-1"
REGIMES=("RISING","FALLING","SIDEWAYS")
NOTICE="Prospective price-only evidence, 30 bps illustrative friction per side. Two disjoint publication/outcome windows; current-registry selected watches, not independent alpha or optimized allocation weights."

def summarize(rows,today,lanes,regime,truncated=False):
    result={"methodology":VERSION,"regime":regime,"status":"AWAITING_COMPARABLE_REGIME_EVIDENCE","lanes":{},"qualified":False,"notice":NOTICE}
    if regime not in REGIMES or truncated:return result
    # Both intervals are already mature; their outcome intervals cannot
    # overlap even with the seven-day exit tolerance.
    blocks=((today-timedelta(days=254),today-timedelta(days=195)),(today-timedelta(days=127),today-timedelta(days=68)))
    grouped=defaultdict(dict)
    for row in rows:
        try:
            e=json.loads(row["evidence"]);isin=e.get("isin")
            if e.get("methodology")!="MULTI-STRATEGY-PROSPECTIVE-1" or e.get("regime_policy")!=VERSION or e.get("regime")!=regime or not exact_isin(isin):continue
            published=rel._stamp(row["published_at"]);maturity=date.fromisoformat(row["maturity_date"])
            if maturity!=published+timedelta(days=60):continue
            block=next((i for i,(a,b) in enumerate(blocks) if a<=published<=b),None)
            if block is None:continue
            ret=rel._outcome(row,published,maturity,today)
            benchmark=rel._index_change(row,ret) if ret is not None else None
            excess=100*((1+ret)*.997**2-1-benchmark) if benchmark is not None else None
            for lane in set(e.get("strategies",[]))&set(lanes):
                # first publication per exact company per lane per window;
                # missing outcomes remain in denominators.
                g=grouped[(lane,block)]
                if isin not in g or published<g[isin][0]:g[isin]=(published,excess)
        except (ValueError,TypeError,KeyError,OverflowError,AttributeError):continue
    for lane in lanes:
        observations=[]
        for i,(a,b) in enumerate(blocks):
            cohort=list(grouped[(lane,i)].values())
            paired=[(day,x) for day,x in cohort if x is not None]
            coverage=len(paired)/len(cohort) if cohort else 0
            ready=len(paired)>=20 and len({day for day,_ in paired})>=10 and coverage>=.8
            observations.append({"publication_start":a.isoformat(),"publication_end":b.isoformat(),"mature_companies":len(cohort),"paired_companies":len(paired),"paired_coverage_percent":round(100*coverage,2),"median_net_excess_pp":round(median(x for _,x in paired),4) if paired else None,"comparable":ready})
        old,recent=observations
        state="UNVALIDATED"
        if recent["comparable"] and recent["median_net_excess_pp"]<=0:state="CAUTION"
        elif all(v["comparable"] and v["median_net_excess_pp"]>0 for v in observations):state="CONSISTENT_DESCRIPTIVE_SUPPORT"
        result["lanes"][lane]={"state":state,"windows":observations}
    if any(v["state"]!="UNVALIDATED" for v in result["lanes"].values()):result["status"]="OBSERVED_REGIME_PRIORITY_CONTEXT"
    return result

def read(connect,instant,lanes,regime):
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    with closing(connect()) as db:
        w._table(db)
        rows=db.execute("SELECT * FROM watch_outcomes WHERE horizon='MULTI_STRATEGY' AND published_at BETWEEN ? AND ? ORDER BY published_at,instrument_id LIMIT 5001",((instant-timedelta(days=366)).isoformat(),instant.isoformat())).fetchall()
    return summarize(rows[:5000],today,lanes,regime,len(rows)>5000)

def priority(strategies,context):
    states=context.get("lanes",{})
    observed=[states.get(k,{}).get("state") for k in strategies]
    return "CAUTION" if "CAUTION" in observed else "SUPPORTED_CONTEXT" if "CONSISTENT_DESCRIPTIVE_SUPPORT" in observed else "UNVALIDATED"
