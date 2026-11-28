"""Scheduler-owned immutable public historical-fund research publications."""
from contextlib import closing
from datetime import date,timedelta
from decimal import Decimal,InvalidOperation
from math import isfinite
from statistics import mean,median
from zoneinfo import ZoneInfo
import json
import re
import sqlite3
from . import nav_catalog
from .fund_categories import COMPARABLE,LABELS
from .market_client import backend_json

VERSION="MF-PROSPECTIVE-1"
DAYS=90
IST=ZoneInfo("Asia/Kolkata")
NOTICE=("Frozen historical peer shortlist only; 90-calendar-day review from actual publication. "
        "First official AMFI NAV strictly after publication and first on/after maturity, each within seven days. "
        "Original observed NAV must still agree. Exact current scheme identity and official NAV path, "
        "not independent historical fund-event or merger verification. No transaction, exit-load, tax, "
        "benchmark-adjusted return or calibrated confidence. Missing mature cases remain in the denominator.")

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS mf_prospective_watch(
        isin TEXT NOT NULL, observed_date TEXT NOT NULL, category TEXT NOT NULL,
        scheme_code TEXT NOT NULL, published_date TEXT NOT NULL,published_at TEXT NOT NULL,
        maturity_date TEXT NOT NULL,evidence TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',
        outcome TEXT,PRIMARY KEY(isin,observed_date))""")
    db.execute("CREATE INDEX IF NOT EXISTS mf_prospective_due ON mf_prospective_watch(status,maturity_date)")
    db.execute("""CREATE TRIGGER IF NOT EXISTS mf_prospective_immutable BEFORE UPDATE ON mf_prospective_watch
        WHEN OLD.status<>'PENDING' OR NEW.isin<>OLD.isin OR NEW.observed_date<>OLD.observed_date
          OR NEW.category<>OLD.category OR NEW.scheme_code<>OLD.scheme_code OR NEW.published_date<>OLD.published_date
          OR NEW.published_at<>OLD.published_at OR NEW.maturity_date<>OLD.maturity_date OR NEW.evidence<>OLD.evidence
        BEGIN SELECT RAISE(ABORT,'immutable fund watch'); END""")

def nav(value):
    if isinstance(value,bool):raise ValueError("NAV")
    n=Decimal(str(value))
    if not n.is_finite() or not Decimal(0)<n<=Decimal("1000000000"):raise ValueError("NAV")
    return n

def valid_score(v):
    return type(v) in (int,float) and isfinite(v) and 50<=v<=100

def decision_states(report,today):
    from . import decision_quality as q
    result={};duplicates=set()
    if not isinstance(report,dict) or report.get("research_date")!=today.isoformat() or report.get("status")!="RESEARCH_AVAILABLE" or q.obj(report.get("decision_quality")).get("methodology")!=q.VERSION:return {}
    for group in q.rows(report.get("funds")):
        if not isinstance(group,dict) or group.get("category") not in COMPARABLE:continue
        for item in q.rows(group.get("items"))[:5]:
            if not isinstance(item,dict) or item.get("qualified") is not False:continue
            quality=q.obj(item.get("decision_quality"));state=quality.get("state")
            if quality.get("methodology")!=q.VERSION or quality.get("qualified") is not False or state not in ("PRIORITY_RESEARCH","EVIDENCE_INCOMPLETE","REVIEW_REQUIRED"):continue
            key=(group["category"],item.get("identifier"),item.get("nav_date"))
            if not all(isinstance(k,str) for k in key):continue
            if key in result:duplicates.add(key)
            from .fund_local_evidence import SEGMENTS
            b=q.obj(q.obj(item.get("fund_evidence")).get("benchmark_context"))
            # A fixed category proxy, not an assumed historical fund mandate.
            benchmark=b.get("benchmark") if b.get("benchmark")==SEGMENTS.get(group["category"]) and b.get("basis") in ("MATCHED_LOCAL_TRI_EXPORT","MATCHED_AUTHORIZED_DIRECT_TRI_CSV") else None
            result[key]={"state":state,"benchmark":benchmark}
    return {k:v for k,v in result.items() if k not in duplicates}

def publish(snapshot,instant,connect=None,*,final_report=None):
    connect=connect or nav_catalog._connect
    if not snapshot.get("enabled") or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return 0
    today=instant.astimezone(IST).date();written=0
    decisions=decision_states(final_report,today)
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db);db.execute("BEGIN IMMEDIATE")
        for section in snapshot.get("sections",[]):
            cat=section.get("section")
            if cat not in COMPARABLE or section.get("status")!="READY":continue
            r=section.get("result") or {};fit=r.get("filters") or {};s=r.get("historical_research_shortlist") or {}
            if fit!={"horizon_months":60,"risk_tolerance":"MODERATE"} or s.get("methodology")!="MF-MATCHED-PEER-1" or s.get("category")!=cat or s.get("status")!="HISTORICAL_SHORTLIST_AVAILABLE":continue
            count=s.get("matched_count")
            if type(count) is not int or not 5<=count<=40:continue
            for item in s.get("items",[])[:5]:
                try:
                    isin=item["isin_growth"];code=item["identifier"];observed=date.fromisoformat(item["nav_date"])
                    if not isinstance(isin,str) or not re.fullmatch(r"INF[A-Z0-9]{9}",isin) or not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{0,8}",code) or not valid_score(item["score"]):continue
                    if item.get("qualified") is not False or item.get("status")!="HISTORICAL_RESEARCH_ONLY" or item["nav_date"]!=s.get("last_date") or not 0<=(today-observed).days<=7:continue
                    original=nav(item["nav"])
                    if db.execute("SELECT 1 FROM mf_prospective_watch WHERE isin=? AND maturity_date>=? LIMIT 1",(isin,(today-timedelta(days=7)).isoformat())).fetchone():continue
                    e={"methodology":VERSION,"score":item["score"],"nav":str(original),"cohort_count":count,
                       "relative_risk":item.get("relative_risk"),"date_digest":s.get("date_digest")}
                    decision=decisions.get((cat,code,observed.isoformat()))
                    if decision:
                        from .decision_quality import VERSION as decision_version
                        e.update(decision_policy=decision_version,decision_state=decision["state"])
                        if decision["benchmark"]:e["category_tri_proxy"]=decision["benchmark"]
                    if not isinstance(e["date_digest"],str) or not re.fullmatch(r"[a-f0-9]{64}",e["date_digest"]):continue
                    written+=db.execute("""INSERT OR IGNORE INTO mf_prospective_watch
                      (isin,observed_date,category,scheme_code,published_date,published_at,maturity_date,evidence)
                      VALUES(?,?,?,?,?,?,?,?)""",(isin,observed.isoformat(),cat,code,today.isoformat(),instant.isoformat(),(today+timedelta(days=DAYS)).isoformat(),json.dumps(e,allow_nan=False))).rowcount
                except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError):continue
    return written

def evaluate(row,payload,today):
    try:
        published=date.fromisoformat(row["published_date"]);maturity=date.fromisoformat(row["maturity_date"]);observed=date.fromisoformat(row["observed_date"])
        e=json.loads(row["evidence"]);identity=payload.get("identity") or {}
        if maturity!=published+timedelta(days=DAYS) or not 0<=(published-observed).days<=7 or today<=maturity+timedelta(days=7) or e.get("methodology")!=VERSION:return None
        if payload.get("status")!="LOCAL_AMFI_OBSERVATIONS" or str(identity.get("scheme_code"))!=row["scheme_code"] or identity.get("isin_growth")!=row["isin"] or identity.get("amfi_plan")!="DIRECT" or identity.get("amfi_option")!="GROWTH" or not str(identity.get("category","")).lower().strip().endswith(" - "+LABELS[row["category"]]+")"):return None
        if not 0<=(today-date.fromisoformat(identity["amfi_metadata_date"])).days<=7:return None
        rows=payload.get("rows")
        if not isinstance(rows,list) or not 3<=len(rows)<=121:return None
        points={};prior=None
        for r in rows:
            d=date.fromisoformat(r["nav_date"])
            if not observed<=d<=maturity+timedelta(days=7) or prior is not None and d<=prior or r.get("source_code")!="AMFI":return None
            points[d]=nav(r["nav"]);prior=d
        if observed not in points or points[observed]!=nav(e["nav"]):return None
        starts=[d for d in points if published<d<=published+timedelta(days=7)]
        ends=[d for d in points if maturity<=d<=maturity+timedelta(days=7)]
        if not starts or not ends:return None
        start,end=min(starts),min(ends)
        path=[d for d in points if start<=d<=end]
        if len(path)<50 or any((b-a).days>14 for a,b in zip(path,path[1:])):return None
        peak=points[start];dd=Decimal(0)
        for d in path:
            peak=max(peak,points[d]);dd=min(dd,points[d]/peak-1)
        return {"status":"OBSERVED_AMFI_NAV_CASE","start_date":start.isoformat(),"end_date":end.isoformat(),
            "start_nav":str(points[start]),"end_nav":str(points[end]),"observations":len(path),
            "nav_change_percent":round(float(100*(points[end]/points[start]-1)),6),"observed_drawdown_percent":round(float(100*dd),6)}
    except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError,ZeroDivisionError,AttributeError):return None

def paired_tri(row,outcome,series,source_basis):
    """Exact endpoints only; no interpolation or price-index substitution."""
    from .fund_local_evidence import SEGMENTS
    try:
        e=json.loads(row["evidence"]);name=e.get("category_tri_proxy")
        if not name or name!=SEGMENTS.get(row["category"]) or source_basis not in ("AUTHORIZED_DIRECT_CSV","AUTHORIZED_LOCAL_EXPORT"):return None
        start,end=date.fromisoformat(outcome["start_date"]),date.fromisoformat(outcome["end_date"])
        values=series.get(name,{})
        a,b=nav(values[start]),nav(values[end])
        change=float(100*(b/a-1))
        if not isfinite(change) or not -100<change<=1e6:return None
        return {"methodology":"FROZEN-CATEGORY-TRI-1","source_basis":source_basis,"benchmark":name,"start_date":start.isoformat(),"end_date":end.isoformat(),"start_tri":str(a),"end_tri":str(b),"tri_change_percent":round(change,6)}
    except (KeyError,ValueError,TypeError,InvalidOperation,OverflowError,AttributeError):return None

def refresh(snapshot,instant,connect=None,loader=backend_json,*,final_report=None):
    connect=connect or nav_catalog._connect
    publish(snapshot,instant,connect,final_report=final_report)
    today=instant.astimezone(IST).date()
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db)
        # Very old unresolved entries become explicit gaps, without querying
        # outside the service's fixed historical bound.
        db.execute("""UPDATE mf_prospective_watch SET status='EVIDENCE_GAP'
            WHERE status='PENDING' AND maturity_date<?""",((today-timedelta(days=270)).isoformat(),))
        due=[dict(r) for r in db.execute("""SELECT * FROM mf_prospective_watch WHERE status='PENDING' AND maturity_date<?
            ORDER BY maturity_date,isin LIMIT 5""",((today-timedelta(days=7)).isoformat(),))]
    series=None
    for row in due:
        maturity=date.fromisoformat(row["maturity_date"])
        try:
            payload=loader("/api/v1/mutual-funds/outcome-window?schemeCode="+row["scheme_code"]+"&from="+row["observed_date"]+"&through="+(maturity+timedelta(days=7)).isoformat())
        except Exception:
            continue # transient local service outage is not a fund outcome
        if not isinstance(payload,dict):continue
        result=evaluate(row,payload,today)
        if result is None and today<=maturity+timedelta(days=14):continue
        if result and json.loads(row["evidence"]).get("category_tri_proxy"):
            if series is None:
                from . import fund_local_evidence as local,official_tri
                try:series=official_tri.combine(local.load(today),official_tri.read(instant),official_tri.local_csv_exports(today))
                except (OSError,ValueError,TypeError,KeyError,AttributeError,sqlite3.Error):series={}
            name=json.loads(row["evidence"]).get("category_tri_proxy")
            basis="AUTHORIZED_DIRECT_CSV" if name in series.get("downloaded_tri_provenance",{}) else "AUTHORIZED_LOCAL_EXPORT"
            pair=paired_tri(row,result,series.get("indices",{}),basis)
            if pair:result["category_tri_comparison"]=pair
        with nav_catalog._LOCK,closing(connect()) as db,db:
            _table(db);db.execute("UPDATE mf_prospective_watch SET status=?,outcome=? WHERE isin=? AND observed_date=? AND status='PENDING'",
                ("OBSERVED" if result else "EVIDENCE_GAP",json.dumps(result,allow_nan=False) if result else None,row["isin"],row["observed_date"]))

def summary(category,today,connect=None):
    connect=connect or nav_catalog._connect
    if category not in COMPARABLE:return {"status":"CATEGORY_SPECIFIC_MODEL_REQUIRED","bands":[],"notice":NOTICE}
    with nav_catalog._LOCK,closing(connect()) as db,db:
        _table(db)
        rows=db.execute("""SELECT * FROM mf_prospective_watch WHERE category=? AND published_date>=?
            ORDER BY published_date,isin LIMIT 1001""",(category,(today-timedelta(days=365)).isoformat())).fetchall()
    from .decision_quality import VERSION as decision_version
    bands=[];immature=0;selected=[];decisions={k:{"published":0,"mature":0,"observed":[],"paired":[]} for k in ("PRIORITY_RESEARCH","EVIDENCE_INCOMPLETE","REVIEW_REQUIRED")}
    for r in rows[:1000]:
        try:
            maturity=date.fromisoformat(r["maturity_date"]);e=json.loads(r["evidence"]);score=e["score"]
            if not valid_score(score) or e.get("methodology")!=VERSION:continue
            state=e.get("decision_state") if e.get("decision_policy")==decision_version else None
            if state in decisions:decisions[state]["published"]+=1
            if today<=maturity+timedelta(days=7):immature+=1;continue
            outcome=json.loads(r["outcome"]) if r["status"]=="OBSERVED" and r["outcome"] else {}
            selected.append((r["isin"],r["published_date"],score,outcome))
            if state in decisions:
                d=decisions[state];d["mature"]+=1
                if outcome.get("status")=="OBSERVED_AMFI_NAV_CASE" and all(type(outcome.get(k)) in (int,float) and isfinite(outcome[k]) for k in ("nav_change_percent","observed_drawdown_percent")):
                    d["observed"].append(outcome["nav_change_percent"])
                    from . import fund_local_evidence as local,official_tri
                    pair=outcome.get("category_tri_comparison") or {}
                    if ((pair.get("source_basis")=="AUTHORIZED_LOCAL_EXPORT" and local.permitted()) or (pair.get("source_basis")=="AUTHORIZED_DIRECT_CSV" and official_tri.permitted())) and pair.get("methodology")=="FROZEN-CATEGORY-TRI-1" and pair.get("benchmark")==e.get("category_tri_proxy")==local.SEGMENTS.get(category) and pair.get("start_date")==outcome.get("start_date") and pair.get("end_date")==outcome.get("end_date"):
                        try:
                            change=float(100*(nav(pair["end_tri"])/nav(pair["start_tri"])-1))
                            if isfinite(change) and abs(change-pair["tri_change_percent"])<=.000001:d["paired"].append((r["isin"],r["published_date"],outcome["nav_change_percent"]-change))
                        except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError):pass
        except (ValueError,TypeError,KeyError):continue
    for name,lo,hi in (("50_TO_BELOW_65",50,65),("65_TO_BELOW_80",65,80),("80_OR_ABOVE",80,101)):
        cohort=[r for r in selected if lo<=r[2]<hi]
        observed=[r for r in cohort if r[3].get("status")=="OBSERVED_AMFI_NAV_CASE" and all(type(r[3].get(k)) in (int,float) and isfinite(r[3][k]) for k in ("nav_change_percent","observed_drawdown_percent"))]
        returns=[r[3]["nav_change_percent"] for r in observed];coverage=len(observed)/len(cohort) if cohort else 0
        bands.append({"band":name,"mature_count":len(cohort),"observed_count":len(observed),"coverage_percent":round(coverage*100,2),
            "distinct_schemes":len({r[0] for r in observed}),"publication_dates":len({r[1] for r in observed}),
            "mean_nav_change_percent":round(mean(returns),4) if returns else None,"median_nav_change_percent":round(median(returns),4) if returns else None,
            "worst_observed_drawdown_percent":min(r[3]["observed_drawdown_percent"] for r in observed) if observed else None})
    decision_summary={k:{"published":v["published"],"mature":v["mature"],"observed":len(v["observed"]),"coverage_percent":round(100*len(v["observed"])/v["mature"],2) if v["mature"] else 0,"median_nav_change_percent":round(median(v["observed"]),4) if v["observed"] else None,
        "matched_tri_count":len(v["paired"]),"median_nav_minus_tri_pp":round(median(x[2] for x in v["paired"]),4) if v["paired"] else None,
        "tri_review_status":"ADVERSE_DESCRIPTIVE_SAMPLE" if len(rows)<=1000 and len(v["paired"])>=20 and len({x[0] for x in v["paired"]})>=15 and len({x[1] for x in v["paired"]})>=10 and len(v["paired"])/v["mature"]>=.8 and median(x[2] for x in v["paired"])<=0 else "NO_ADVERSE_SAMPLE_ESTABLISHED"} for k,v in decisions.items()}
    return {"decision_policy":decision_version,"decision_states":decision_summary,"status":"DESCRIPTIVE_OBSERVED_OUTCOMES" if any(b["observed_count"] for b in bands) else "AWAITING_MATURE_EVIDENCE",
        "mature_count":len(selected),"immature_count":immature,"truncated":len(rows)>1000,"bands":bands,"calibrated":False,"notice":NOTICE}
