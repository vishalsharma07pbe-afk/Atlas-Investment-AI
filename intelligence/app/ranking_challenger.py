"""Paired fixed-priority versus adaptive-priority prospective experiment.

One pair per seven days; no extra immediate provider calls, no historical
backfill. Same venue/session, immutable publications, existing outcome worker.
"""
from contextlib import closing
from datetime import date,timedelta
from statistics import median
from zoneinfo import ZoneInfo
from hashlib import sha256
import json,re
from . import watch_outcomes as w,research_reliability as rel
from .replay_evidence import exact_isin

VERSION="RANKING-CHALLENGER-1"
HORIZON="RANKING_CHALLENGER"
NOTICE="Paired distinct top-ranked candidates from the same eligible snapshot, fixed versus adaptive ordering. 60-calendar-day price changes after illustrative 30 bps each side. Identical outcome endpoints required; overlapping time windows and nonrandom selections limit inference. No automatic promotion."

def selection(items,order):
    # Exclude unadjusted candidates from both arms before comparing.
    eligible=[r for r in items if r.get("adjustment_verified_for_screen") is True and r.get("publication_regime") in ("RISING","FALLING","SIDEWAYS") and exact_isin(r.get("isin"))]
    if not eligible:return {"status":"AWAITING_COMPARABLE_CANDIDATES"}
    fixed=min(eligible,key=lambda r:order(r)[1:])
    adaptive=min(eligible,key=order)
    if fixed["isin"]==adaptive["isin"]:return {"status":"SAME_SELECTION"}
    if any(fixed.get(k)!=adaptive.get(k) for k in ("exchange","as_of","publication_regime")):return {"status":"NONCOMPARABLE_SELECTIONS"}
    keys=("id","isin","symbol","exchange","as_of","close")
    return {"status":"DISTINCT_PAIRED_SELECTION","fixed":{k:fixed[k] for k in keys},"adaptive":{k:adaptive[k] for k in keys},"regime":fixed["publication_regime"],"qualified":False}

def publish(snapshot,connect,instant):
    if snapshot.get("enabled") is not True or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return 0
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    if snapshot.get("research_date")!=today.isoformat():return 0
    report=snapshot.get("multi_strategy") or {};p=report.get("ranking_experiment") or {}
    if p.get("status")!="DISTINCT_PAIRED_SELECTION" or p.get("qualified") is not False:return 0
    arms=[p.get("fixed"),p.get("adaptive")]
    try:
        if not all(isinstance(r,dict) and exact_isin(r.get("isin")) and type(r.get("id")) is int and r["id"]>0 and r["exchange"] in ("NSE","BSE") and re.fullmatch(r"[A-Z0-9._&-]{1,50}",r["symbol"]) and type(r["close"]) in (int,float) and 0<r["close"]<=1e9 and 1<=(today-date.fromisoformat(r["as_of"])).days<=4 for r in arms):return 0
        a,b=arms
        if a["isin"]==b["isin"] or a["id"]==b["id"] or a["exchange"]!=b["exchange"] or a["as_of"]!=b["as_of"]:return 0
    except (ValueError,TypeError,KeyError):return 0
    with closing(connect()) as db,db:
        w._table(db);db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM watch_outcomes WHERE horizon=? AND published_at>=? LIMIT 1",(HORIZON,(instant-timedelta(days=7)).isoformat())).fetchone():return 0
        pair=sha256((instant.isoformat()+"|"+a["isin"]+"|"+b["isin"]).encode()).hexdigest()
        for role,r in zip(("FIXED","ADAPTIVE"),arms):
            e={k:r[k] for k in ("isin","symbol","exchange","as_of","close")}
            e.update(methodology=VERSION,adjustment_status="ADJUSTED",pair=pair,arm=role,regime=p.get("regime"))
            if db.execute("SELECT 1 FROM watch_outcomes WHERE instrument_id=? AND horizon=? AND observed_date=?",(r["id"],HORIZON,r["as_of"])).fetchone():return 0
        # Both rows commit atomically or neither.
        for role,r in zip(("FIXED","ADAPTIVE"),arms):
            e={k:r[k] for k in ("isin","symbol","exchange","as_of","close")}
            e.update(methodology=VERSION,adjustment_status="ADJUSTED",pair=pair,arm=role,regime=p.get("regime"))
            db.execute("INSERT INTO watch_outcomes(instrument_id,horizon,observed_date,published_at,maturity_date,evidence) VALUES(?,?,?,?,?,?)",(r["id"],HORIZON,r["as_of"],instant.isoformat(),(today+timedelta(days=60)).isoformat(),json.dumps(e,allow_nan=False)))
    return 2

def summary(connect,instant):
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    with closing(connect()) as db:
        w._table(db)
        rows=db.execute("SELECT * FROM watch_outcomes WHERE horizon=? AND published_at BETWEEN ? AND ? ORDER BY published_at,instrument_id LIMIT 501",(HORIZON,(instant-timedelta(days=366)).isoformat(),instant.isoformat())).fetchall()
    groups={}
    for row in rows[:500]:
        try:
            e=json.loads(row["evidence"])
            if e.get("methodology")!=VERSION or not exact_isin(e.get("isin")) or e.get("arm") not in ("FIXED","ADAPTIVE") or not re.fullmatch(r"[a-f0-9]{64}",e.get("pair","")):continue
            groups.setdefault(e["pair"],[]).append((row,e))
        except (ValueError,TypeError,KeyError):continue
    mature=0;paired=[];distinct=set()
    for pair in groups.values():
        if len(pair)!=2 or {e["arm"] for _,e in pair}!={"FIXED","ADAPTIVE"}:continue
        try:
            pair.sort(key=lambda x:x[1]["arm"]);(a,ae),(f,fe)=pair
            if ae["isin"]==fe["isin"] or any(ae[k]!=fe[k] for k in ("exchange","as_of","regime")) or a["published_at"]!=f["published_at"] or a["maturity_date"]!=f["maturity_date"]:continue
            start=rel._stamp(a["published_at"]);end=date.fromisoformat(a["maturity_date"])
            if end!=start+timedelta(days=60) or today<=end+timedelta(days=7):continue
            mature+=1
            x,y=rel._outcome(a,start,end,today),rel._outcome(f,start,end,today)
            if x is None or y is None:continue
            ao,fo=json.loads(a["outcome"]),json.loads(f["outcome"])
            if any(ao[k]!=fo[k] for k in ("entry_date","exit_date","observations")):continue
            paired.append(100*(x-y)*.997**2);distinct.update((ae["isin"],fe["isin"]))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):continue
    return {"methodology":VERSION,"status":"PAIRED_DESCRIPTIVE_OUTCOMES" if paired else "AWAITING_MATURE_PAIRS","published_pairs":len(groups),"mature_pairs":mature,"observed_pairs":len(paired),
        "distinct_companies":len(distinct),"median_adaptive_minus_fixed_net_pp":round(median(paired),4) if paired else None,"adaptive_win_count":sum(v>0 for v in paired),"truncated":len(rows)>500,"qualified":False,"notice":NOTICE}
