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
    comparable=defaultdict(list);eligible_days=set();required_groups=defaultdict(int)
    for (day,group),rows in sorted(cohorts.items()):
        if not all(rows.values()):continue
        eligible_days.add(day);required_groups[day]+=1
        # Require entire pair/basket observed and identical endpoints.
        both=rows["CONDITIONAL"]+rows["WITHHELD"]
        if not all(number(r.get("net")) and number(r.get("stress")) and r.get("endpoints") for r in both):continue
        if len({r["endpoints"] for r in both})!=1:continue
        delta=mean(r["net"] for r in rows["CONDITIONAL"])-mean(r["net"] for r in rows["WITHHELD"])
        stress=mean(r["stress"] for r in rows["CONDITIONAL"])-mean(r["stress"] for r in rows["WITHHELD"])
        comparable[day].append((delta,stress))
    # One equal-weight date observation; multiple venues do not multiply evidence.
    dates={d:(mean(v[0] for v in x),mean(v[1] for v in x)) for d,x in comparable.items() if len(x)==required_groups[d]}
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


# Record first scheduled public observation per day, including no-action days.
# This denominator is scheduler observations, NOT exchange trading sessions.
from contextlib import closing
from datetime import date
from zoneinfo import ZoneInfo
import json

SCOPES=("STOCK","LARGE_CAP","MID_CAP","SMALL_CAP")
def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS final_action_day(
        policy TEXT NOT NULL,observed_day TEXT NOT NULL,captured_at TEXT NOT NULL,
        evidence TEXT NOT NULL,PRIMARY KEY(policy,observed_day))""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS final_action_day_immutable
        BEFORE UPDATE ON final_action_day BEGIN SELECT RAISE(ABORT,'immutable daily action audit'); END""")

def capture(snapshot,connect,instant):
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return False
    day=instant.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    if snapshot.get("research_date")!=day:return False
    report=snapshot.get("investment_analyst") or {}
    from . import decision_quality as q
    policy=q.obj(report.get("decision_quality"))
    status=report.get("status")
    if status not in ("RESEARCH_AVAILABLE","NO_SUPPORTED_CANDIDATES","AWAITING_CURRENT_RESEARCH","UNAVAILABLE"):return False
    counts={k:{"candidates":0,"conditional":0} for k in SCOPES}
    valid=report.get("research_date")==day and policy.get("methodology")==q.VERSION and policy.get("status")!="UNAVAILABLE"
    def add(scope,rows,action):
        for r in q.rows(rows):
            if not isinstance(r,dict) or r.get("qualified") is not False:continue
            counts[scope]["candidates"]+=1
            d=q.obj(r.get("decision_quality"))
            held=policy.get("forecast_allocation_hold") or (policy.get("stock_allocation_hold") if scope=="STOCK" else scope in q.rows(policy.get("fund_allocation_holds")))
            if valid and not held and not r.get("allocation_evidence_hold") and r.get("action")==action and d.get("state")=="PRIORITY_RESEARCH" and d.get("methodology")==q.VERSION and d.get("qualified") is False:
                counts[scope]["conditional"]+=1
    add("STOCK",report.get("stocks"),"RESEARCH_FOR_ENTRY")
    for g in q.rows(report.get("funds")):
        if isinstance(g,dict) and g.get("category") in SCOPES[1:]:add(g["category"],g.get("items"),"COMPARE_FOR_SIP")
    evidence={"status":status,"policy_available":bool(valid),"counts":counts}
    with closing(connect()) as db,db:
        _table(db)
        return db.execute("INSERT OR IGNORE INTO final_action_day VALUES(?,?,?,?)",(VERSION,day,instant.isoformat(),json.dumps(evidence,allow_nan=False))).rowcount==1

def daily_summary(connect,today):
    with closing(connect()) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='final_action_day'").fetchone():rows=[]
        else:rows=db.execute("SELECT * FROM final_action_day WHERE policy=? AND observed_day BETWEEN ? AND ? ORDER BY observed_day",(VERSION,(today-timedelta(days=364)).isoformat(),today.isoformat())).fetchall()
    scopes={k:{"days_with_candidates":0,"days_with_conditional_action":0} for k in SCOPES}
    unavailable=0;no_supported=0;valid_days=[]
    for row in rows:
        try:
            e=json.loads(row["evidence"]);counts=e["counts"]
            if not all(type(counts[k]["candidates"]) is int and type(counts[k]["conditional"]) is int and 0<=counts[k]["conditional"]<=counts[k]["candidates"]<=100 for k in SCOPES):continue
            day=date.fromisoformat(row["observed_day"])
            valid_days.append(day)
            if e.get("status")=="NO_SUPPORTED_CANDIDATES":no_supported+=1
            elif e.get("policy_available") is not True:unavailable+=1
            for k in SCOPES:
                scopes[k]["days_with_candidates"]+=counts[k]["candidates"]>0
                scopes[k]["days_with_conditional_action"]+=counts[k]["conditional"]>0
        except (ValueError,TypeError,KeyError,AttributeError):continue
    n=len(valid_days)
    return {"status":"OBSERVED_SCHEDULED_DAYS" if n else "AWAITING_SCHEDULED_OBSERVATIONS","observed_days":n,
        "policy_unavailable_days":unavailable,"no_supported_candidate_days":no_supported,"first_day":min(valid_days).isoformat() if n else None,
        "last_day":max(valid_days).isoformat() if n else None,"calendar_days_without_observation":(max(valid_days)-min(valid_days)).days+1-n if n else None,
        "scopes":scopes,"notice":"First scheduled public report per observed day; not all market sessions or intraday decisions. No-action and unavailable observations retained."}
