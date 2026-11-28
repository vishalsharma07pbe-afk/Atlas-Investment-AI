"""Immutable actual analyst-decision cohort, using existing audited outcomes.

Only exact adjusted joint-screen candidates; no historical backfill and no
private holdings. Fixed 60-calendar-day review, not executed returns.
"""
from contextlib import closing
from collections import defaultdict
from datetime import date,timedelta
from statistics import mean,median
from zoneinfo import ZoneInfo
import json,re
from . import decision_quality as q,watch_outcomes as w,research_reliability as rel
from .replay_evidence import exact_isin

VERSION="ANALYST-DECISION-OUTCOMES-1"
HORIZON="ANALYST_DECISION"
STATES=("PRIORITY_RESEARCH","EVIDENCE_INCOMPLETE","REVIEW_REQUIRED")
IST=ZoneInfo("Asia/Kolkata")
NOTICE="Frozen adjusted joint-screen decision categories, 60-calendar-day price observations. Same-date price-index comparison after illustrative 30 bps per side. Nonrandom current candidates, not portfolio returns or calibrated predictive performance."

def publish(report,connect,instant):
    today=instant.astimezone(IST).date()
    if report.get("research_date")!=today.isoformat() or report.get("status")!="RESEARCH_AVAILABLE" or q.obj(report.get("decision_quality")).get("methodology")!=q.VERSION:return 0
    count=0
    with closing(connect()) as db,db:
        w._table(db);db.execute("BEGIN IMMEDIATE")
        recent=db.execute("SELECT evidence,published_at FROM watch_outcomes WHERE horizon=? AND published_at>=?",(HORIZON,(instant-timedelta(days=68)).isoformat())).fetchall()
        existing=set();daily=set()
        for r in recent:
            try:
                e=json.loads(r["evidence"])
                existing.add(e["isin"])
                if rel._stamp(r["published_at"])==today:daily.add(e["decision_state"])
            except (ValueError,TypeError,KeyError):continue
        for r in q.rows(report.get("stocks"))[:10]:
            d=q.obj(r.get("decision_quality"));state=d.get("state")
            if state not in STATES or state in daily or d.get("methodology")!=q.VERSION or d.get("qualified") is not False or r.get("qualified") is not False or r.get("tier")!="ADJUSTED_JOINT":continue
            isin=r.get("isin")
            if not exact_isin(isin) or isin in existing or not q.fresh(r.get("as_of"),today,1,4):continue
            if type(r.get("id")) is not int or r["id"]<=0 or r.get("exchange") not in ("NSE","BSE") or not isinstance(r.get("symbol"),str) or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",r["symbol"]) or not q.num(r.get("close"),.0001,1e9):continue
            e={k:r[k] for k in ("isin","symbol","exchange","close","as_of")}
            e.update(methodology=VERSION,decision_policy=q.VERSION,adjustment_status="ADJUSTED",decision_state=state)
            n=db.execute("""INSERT OR IGNORE INTO watch_outcomes(instrument_id,horizon,observed_date,published_at,maturity_date,evidence)
                VALUES(?,?,?,?,?,?)""",(r["id"],HORIZON,r["as_of"],instant.isoformat(),(today+timedelta(days=60)).isoformat(),json.dumps(e,allow_nan=False))).rowcount
            if n:daily.add(state);existing.add(isin);count+=n
    return count

def summarize_rows(rows,today,truncated=False):
    groups=defaultdict(list);published=defaultdict(int)
    for r in rows:
        try:
            e=json.loads(r["evidence"]);state=e.get("decision_state")
            if e.get("methodology")!=VERSION or e.get("decision_policy")!=q.VERSION or state not in STATES or not exact_isin(e.get("isin")):continue
            start=rel._stamp(r["published_at"]);maturity=date.fromisoformat(r["maturity_date"])
            if maturity!=start+timedelta(days=60) or start>today:continue
            published[state]+=1
            if today<=maturity+timedelta(days=7):continue
            ret=rel._outcome(r,start,maturity,today)
            benchmark=rel._index_change(r,ret) if ret is not None else None
            net=100*((1+ret)*.997**2-1) if ret is not None else None
            excess=net-100*benchmark if benchmark is not None else None
            groups[state].append((e["isin"],start,net,excess))
        except (ValueError,TypeError,KeyError,OverflowError,AttributeError):continue
    result={}
    for state in STATES:
        cohort=groups[state];observed=[x for x in cohort if x[2] is not None];paired=[x for x in observed if x[3] is not None]
        coverage=len(observed)/len(cohort) if cohort else 0
        ready=not truncated and len(paired)>=30 and len({x[0] for x in paired})>=20 and len({x[1] for x in paired})>=10 and len(paired)/len(cohort)>=.8
        values=[x[3] for x in paired]
        result[state]={"published":published[state],"mature":len(cohort),"observed":len(observed),"matched_index":len(paired),
            "coverage_percent":round(100*coverage,2),"distinct_observed_companies":len({x[0] for x in observed}),
            "mean_net_price_change_percent":round(mean(x[2] for x in observed),4) if observed else None,
            "median_net_minus_price_index_pp":round(median(values),4) if values else None,
            "status":"INSUFFICIENT_MATURE_COMPARABLE_EVIDENCE" if not ready else "ADVERSE_OBSERVED_SAMPLE" if median(values)<=0 else "POSITIVE_DESCRIPTIVE_SAMPLE"}
    return {"methodology":VERSION,"status":"OBSERVED_DECISION_OUTCOMES" if any(v["observed"] for v in result.values()) else "AWAITING_MATURITY",
        "states":result,"truncated":truncated,"qualified":False,"notice":NOTICE}

def summary(connect,instant):
    with closing(connect()) as db:
        w._table(db)
        rows=db.execute("SELECT * FROM watch_outcomes WHERE horizon=? AND published_at BETWEEN ? AND ? ORDER BY published_at,instrument_id LIMIT 5001",(HORIZON,(instant-timedelta(days=366)).isoformat(),instant.isoformat())).fetchall()
    return summarize_rows(rows[:5000],instant.astimezone(IST).date(),len(rows)>5000)
