"""Frozen prospective quarterly persistence experiment, public company cache only.

This is a baseline model, not analyst consensus, EPS, valuation or a qualified
forecast. No network calls or private portfolio data. Compare with the unchanged
year-ago baseline and preserve missing/revised outcomes in the denominator.
"""
from contextlib import closing
from datetime import date,datetime,timedelta
from math import isfinite
from statistics import mean,median
from collections import defaultdict
from zoneinfo import ZoneInfo
import json
import re
from . import quarterly_financials as q, automatic_company_evidence as company
from .replay_evidence import exact_isin
from .company_venues import collect

VERSION="QUARTER-PERSISTENCE-1"
IST=ZoneInfo("Asia/Kolkata")
METRICS=("revenue","net_profit")
NOTICE=("Experimental next-quarter reported amount baseline: persist the latest year-over-year growth "
        "onto the same quarter one year earlier, versus unchanged year-ago amount. Frozen before target quarter end. "
        "Source is the existing consolidated provider cache, not analyst estimates or independently verified filings. "
        "No price target, EPS estimate, model fitting, confidence, recommendation or qualification. "
        "Missing/revised outcomes remain in denominators; quarterly observations are dependent.")

def _series(report,instant):
    if not isinstance(report,dict) or not exact_isin(report.get("isin")) or report.get("historical_cache_only") is True:return None
    try:
        stamp=datetime.fromisoformat(report["retrieved_at"])
        if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant:return None
        b=report["sections"]["quarterly_income"]
        captured=datetime.fromisoformat(b["source"]["retrieved_at"])
        # Incremental company reports keep the oldest section date at report
        # level. Use the actual quarterly source capture, never refresh it.
        if captured.tzinfo is None or not stamp<=captured<=instant or captured<instant-timedelta(hours=24):return None
        stamp=captured
        today=instant.astimezone(IST).date()
        result=q.summarize(report,today)
        if result["status"] not in ("REPORTED_QUARTERLY_COMPARISONS","PARTIAL_LATEST_QUARTER"):return None
        latest=date.fromisoformat(result["latest_period"])
        if latest.month not in (3,6,9,12):return None
        series={k:{date.fromisoformat(p["period"]):p["value"] for p in b["data"]["series"].get(k,[])} for k in METRICS}
        return stamp,latest,series
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):return None

def baseline(report,instant):
    evidence=_series(report,instant)
    if evidence is None:return None
    stamp,latest,series=evidence
    today=instant.astimezone(IST).date();target=q.shift(latest,3)
    # No late or retrospective publication for a quarter already completed.
    if not latest<today<target:return None
    rows={}
    for metric,p in series.items():
        prior=q.shift(latest,-12);target_prior=q.shift(target,-12)
        a,b,c=(p.get(d) for d in (latest,prior,target_prior))
        if any(type(x) not in (int,float) or not isfinite(x) or not 0<x<=1e12 for x in (a,b,c)):return None
        growth=q.growth(a,b)
        # Bounded experiment; do not winsorize or infer from negative bases.
        if growth is None or not -50<=growth<=100:return None
        estimate=c*(1+growth/100)
        if not 0<estimate<=1e12:return None
        rows[metric]={"latest_amount_cr":a,"latest_prior_year_amount_cr":b,"target_prior_year_amount_cr":c,
                      "persisted_growth_percent":growth,"persistence_amount_cr":round(estimate,6),
                      "unchanged_amount_cr":c}
    return {"methodology":VERSION,"isin":report["isin"],"observed_quarter":latest.isoformat(),"target_quarter":target.isoformat(),
            "capture_at":stamp.isoformat(),"metrics":rows,"qualified":False}

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS earnings_persistence(
      isin TEXT NOT NULL,target_quarter TEXT NOT NULL,published_at TEXT NOT NULL,
      evidence TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',outcome TEXT,
      PRIMARY KEY(isin,target_quarter))""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS earnings_persistence_immutable BEFORE UPDATE ON earnings_persistence
      WHEN OLD.status<>'PENDING' OR NEW.isin<>OLD.isin OR NEW.target_quarter<>OLD.target_quarter OR
        NEW.published_at<>OLD.published_at OR NEW.evidence<>OLD.evidence
      BEGIN SELECT RAISE(ABORT,'immutable earnings baseline'); END""")

def evaluate(row,report,instant):
    data=_series(report,instant)
    if not data or report.get("isin")!=row["isin"]:return None
    stamp,latest,series=data;today=instant.astimezone(IST).date()
    try:
        e=json.loads(row["evidence"]);target=date.fromisoformat(row["target_quarter"])
        published=datetime.fromisoformat(row["published_at"]);old=date.fromisoformat(e["observed_quarter"])
        if published.tzinfo is None or e.get("qualified") is not False or e["methodology"]!=VERSION or e["isin"]!=row["isin"] or e["target_quarter"]!=target.isoformat() or q.shift(old,3)!=target or not old<published.astimezone(IST).date()<target or not target<today or latest<target or stamp<=published:return None
        if any(target not in series[k] for k in METRICS):return None
        rows={}
        for key in METRICS:
            p=series[key];f=e["metrics"][key]
            anchors=(old,q.shift(old,-12),q.shift(target,-12))
            expected=(f["latest_amount_cr"],f["latest_prior_year_amount_cr"],f["target_prior_year_amount_cr"])
            if any(d not in p for d in anchors):return None
            if any(p[d]!=v for d,v in zip(anchors,expected)):return {"status":"REVISED_BASE_EVIDENCE"}
            actual=p[target];base=f["target_prior_year_amount_cr"]
            # Reconcile stored baseline arithmetic before evaluating.
            growth=q.growth(f["latest_amount_cr"],f["latest_prior_year_amount_cr"])
            if growth is None or growth!=f["persisted_growth_percent"] or not -50<=growth<=100 or f["unchanged_amount_cr"]!=base or abs(f["persistence_amount_cr"]-round(base*(1+growth/100),6))>1e-6:return None
            if not 0<base<=1e12:return None
            # Scale by original positive seasonal base, not possibly zero actual.
            a=100*abs(actual-f["persistence_amount_cr"])/base
            b=100*abs(actual-base)/base
            if not all(isfinite(x) and 0<=x<=1e6 for x in (a,b)):return None
            rows[key]={"actual_amount_cr":actual,"persistence_absolute_error_pp":round(a,6),"unchanged_absolute_error_pp":round(b,6)}
        return {"status":"OBSERVED_PROVIDER_QUARTER","observed_at":stamp.isoformat(),"metrics":rows}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,ZeroDivisionError):return None

def due_identities(connect,instant):
    """Only immutable public publications, never private or arbitrary identities."""
    if not company.permitted():return []
    today=instant.astimezone(IST).date()
    try:
        with closing(connect()) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='earnings_persistence'").fetchone():return []
            rows=db.execute("""SELECT * FROM earnings_persistence WHERE status='PENDING'
                AND target_quarter>=? AND target_quarter<? ORDER BY target_quarter,isin LIMIT 100""",
                ((today-timedelta(days=150)).isoformat(),today.isoformat())).fetchall()
        result=[]
        for row in rows:
            try:
                e=json.loads(row["evidence"]);target=date.fromisoformat(row["target_quarter"])
                published=datetime.fromisoformat(row["published_at"]);old=date.fromisoformat(e["observed_quarter"])
                isin=row["isin"]
                if (exact_isin(isin) and e.get("isin")==isin and e.get("methodology")==VERSION
                    and e.get("qualified") is False and e.get("target_quarter")==target.isoformat()
                    and published.tzinfo is not None and published<=instant
                    and old<published.astimezone(IST).date()<target and q.shift(old,3)==target
                    and isin not in result):result.append(isin)
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError):continue
        return result
    except (OSError,ValueError,TypeError,AttributeError,__import__("sqlite3").Error):return []


def refresh(snapshot,connect,instant):
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY" or not company.permitted():return 0
    today=instant.astimezone(IST).date()
    if snapshot.get("research_date")!=today.isoformat():return 0
    # Only public selected daily/Elite candidates; no private portfolio source.
    venues=collect(snapshot,instant)
    ids=sorted({isin for item,isin in company.identify_priority(snapshot)
        if any(r.get("as_of")==item.get("as_of") and r.get("id")==item.get("id") and r.get("exchange")==item.get("exchange")
               and item.get("as_of") is not None for r in venues.get(isin,[]))})[:100]
    with closing(connect()) as db,db:
        _table(db)
        db.execute("UPDATE earnings_persistence SET status='EVIDENCE_GAP' WHERE status='PENDING' AND target_quarter<?",((today-timedelta(days=150)).isoformat(),))
        due=[dict(r) for r in db.execute("SELECT * FROM earnings_persistence WHERE status='PENDING' AND target_quarter<? ORDER BY target_quarter,isin LIMIT 100",(today.isoformat(),))]
    reports=company.cached_action_reports(connect,set(ids)|{r["isin"] for r in due},instant)
    written=0
    with closing(connect()) as db,db:
        _table(db);db.execute("BEGIN IMMEDIATE")
        for isin in ids:
            raw=reports.get(isin)
            if not raw or raw.get("isin")!=isin:continue
            e=baseline(raw,instant)
            if e:
                written+=db.execute("INSERT OR IGNORE INTO earnings_persistence(isin,target_quarter,published_at,evidence) VALUES(?,?,?,?)",
                    (isin,e["target_quarter"],instant.isoformat(),json.dumps(e,allow_nan=False))).rowcount
        for row in due:
            result=evaluate(row,reports.get(row["isin"]),instant)
            if result:
                db.execute("UPDATE earnings_persistence SET status=?,outcome=? WHERE isin=? AND target_quarter=? AND status='PENDING'",
                    ("OBSERVED" if result["status"]=="OBSERVED_PROVIDER_QUARTER" else "REVISED_BASE_EVIDENCE",json.dumps(result,allow_nan=False),row["isin"],row["target_quarter"]))
    return written

def summary(connect,instant):
    out={"methodology":VERSION,"status":"DISABLED_OR_NOT_AUTHORIZED","pending_count":None,"quarter_cohorts":[],"calibrated":False,"notice":NOTICE}
    if not company.permitted():return out
    today=instant.astimezone(IST).date()
    with closing(connect()) as db:
        _table(db);rows=db.execute("SELECT * FROM earnings_persistence WHERE target_quarter>=? ORDER BY target_quarter,isin LIMIT 5001",((today-timedelta(days=730)).isoformat(),)).fetchall()
    groups=defaultdict(list);pending=0
    for row in rows[:5000]:
        if row["status"]=="PENDING" and today<=date.fromisoformat(row["target_quarter"])+timedelta(days=150):pending+=1
        groups[row["target_quarter"]].append(row)
    for quarter,items in sorted(groups.items(),reverse=True):
        # Maturity deadline is predeclared; avoid early success-only statistics.
        if today<=date.fromisoformat(quarter)+timedelta(days=150):continue
        observed=[]
        for row in items:
            if row["status"]!="OBSERVED":continue
            try:
                e=json.loads(row["outcome"])
                if e["status"]!="OBSERVED_PROVIDER_QUARTER" or any(not (type(e["metrics"][k][f]) in (int,float) and isfinite(e["metrics"][k][f]) and 0<=e["metrics"][k][f]<=1e6) for k in METRICS for f in ("persistence_absolute_error_pp","unchanged_absolute_error_pp")):continue
                observed.append(e["metrics"])
            except (ValueError,KeyError,TypeError,AttributeError):continue
        metrics=[]
        for k in METRICS:
            a=[r[k]["persistence_absolute_error_pp"] for r in observed];b=[r[k]["unchanged_absolute_error_pp"] for r in observed]
            metrics.append({"metric":k,"persistence_mean_error_pp":round(mean(a),4) if a else None,
                "unchanged_mean_error_pp":round(mean(b),4) if b else None,
                "persistence_median_error_pp":round(median(a),4) if a else None,
                "lower_error_count":sum(x<y for x,y in zip(a,b))})
        out["quarter_cohorts"].append({"target_quarter":quarter,"published_count":len(items),"observed_count":len(observed),
            "revised_count":sum(r["status"]=="REVISED_BASE_EVIDENCE" for r in items),
            "coverage_percent":round(100*len(observed)/len(items),2),"metrics":metrics,
            "status":"DESCRIPTIVE_SAMPLE_ONLY" if len(rows)<=5000 and len(observed)>=30 and len(observed)/len(items)>=.8 else "INSUFFICIENT_EVIDENCE"})
    out.update(status="PROSPECTIVE_EXPERIMENT" if rows else "AWAITING_PUBLICATIONS",pending_count=pending,truncated=len(rows)>5000)
    return out
