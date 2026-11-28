"""Prospective final-action comparisons, independent of research-readiness scores.

Inputs are already validated original publications and audited outcomes. Do not
backfill action labels, assume missing returns, or interpret these as fills.
"""
from collections import defaultdict
from datetime import timedelta
from math import isfinite
from statistics import mean,median

VERSION="FINAL-ACTION-EFFECTIVENESS-1"
NOTICE="Frozen final research actions, not actual trades. Matched close/NAV endpoints, same publication day and comparable venue/category; missing outcomes stay in denominators. Nonoverlapping time windows selected before observing returns. Descriptive only; no significance, forecast, or certification."

def number(v):
    return type(v) in (int,float) and isfinite(v) and -100<=v<=1e8

def summarize(records,horizon,*,truncated=False):
    # record: day, identity, group, arm, endpoints, net standard-cost return,
    # stress-cost return, same-endpoint benchmark return (percentage points).
    arms={"CONDITIONAL":[],"WITHHELD":[]}
    cohorts=defaultdict(lambda: {"CONDITIONAL":[],"WITHHELD":[]})
    seen=set()
    for r in records:
        arm=r["arm"];key=(r["day"],r["group"],r["identity"])
        if arm not in arms or key in seen:continue
        seen.add(key);arms[arm].append(r);cohorts[(r["day"],r["group"])][arm].append(r)
    result={}
    for arm,rows in arms.items():
        observed=[r for r in rows if number(r.get("net"))]
        paired=[r for r in observed if number(r.get("benchmark"))]
        result[arm]={"mature":len(rows),"observed":len(observed),"matched_benchmark":len(paired),
            "coverage_percent":round(100*len(observed)/len(rows),2) if rows else 0,
            "distinct_companies_or_schemes":len({r["identity"] for r in observed}),
            "median_net_percent":round(median(r["net"] for r in observed),4) if observed else None,
            "median_net_excess_pp":round(median(r["net"]-r["benchmark"] for r in paired),4) if paired else None,
            "median_stress_excess_pp":round(median(r["stress"]-r["benchmark"] for r in paired if number(r.get("stress"))),4) if paired and all(number(r.get("stress")) for r in paired) else None}
    comparable=defaultdict(list);eligible_days=set()
    for (day,group),rows in sorted(cohorts.items()):
        if not all(rows.values()):continue
        eligible_days.add(day)
        # Require entire pair/basket observed and identical endpoints.
        both=rows["CONDITIONAL"]+rows["WITHHELD"]
        if not all(number(r.get("net")) and number(r.get("stress")) and r.get("endpoints") for r in both):continue
        if len({r["endpoints"] for r in both})!=1:continue
        delta=mean(r["net"] for r in rows["CONDITIONAL"])-mean(r["net"] for r in rows["WITHHELD"])
        stress=mean(r["stress"] for r in rows["CONDITIONAL"])-mean(r["stress"] for r in rows["WITHHELD"])
        comparable[day].append((delta,stress))
    # One equal-weight date observation; multiple venues do not multiply evidence.
    dates={d:(mean(v[0] for v in x),mean(v[1] for v in x)) for d,x in comparable.items()}
    # Choose from all eligible publication dates, not just successful outcomes.
    independent=[];last=None
    for day in sorted(eligible_days):
        if last is None or day>last+timedelta(days=horizon+7):
            independent.append(day);last=day
    matched=[dates[d] for d in independent if d in dates]
    def stats(values):
        return {"observed_dates":len(values),"median_net_advantage_pp":round(median(v[0] for v in values),4) if values else None,
            "median_stress_advantage_pp":round(median(v[1] for v in values),4) if values else None,"positive_dates":sum(v[0]>0 for v in values)}
    status="AWAITING_MATURE_ACTIONS" if not any(arms.values()) else "INSUFFICIENT_MATCHED_ACTION_EVIDENCE"
    if not truncated and len(independent)>=3 and len(matched)/len(independent)>=.8:
        status="DESCRIPTIVE_NONOVERLAPPING_COMPARISON"
    return {"methodology":VERSION,"status":status,"arms":result,
        "matched_dates":{"eligible_dates":len(eligible_days),**stats(list(dates.values()))},
        "nonoverlapping_dates":{"eligible_dates":len(independent),**stats(matched)},
        "truncated":truncated,"qualified":False,"notice":NOTICE}
