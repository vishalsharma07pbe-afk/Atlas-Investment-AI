"""Freeze multi-strategy research publications and evaluate through the existing watch ledger."""
from contextlib import closing
from datetime import date,timedelta
import json
from zoneinfo import ZoneInfo
from statistics import mean
from . import watch_outcomes, research_reliability as rel, multi_strategy as m
VERSION="MULTI-STRATEGY-PROSPECTIVE-1"
HORIZON="MULTI_STRATEGY"

def publish(snapshot,connect,instant):
    report=snapshot.get("multi_strategy") or {}
    if report.get("methodology")!=m.VERSION:return 0
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    count=0
    with closing(connect()) as db,db:
        watch_outcomes._table(db)
        db.execute("BEGIN IMMEDIATE")
        existing=set()
        for row in db.execute("SELECT evidence FROM watch_outcomes WHERE horizon=? AND published_at>=?",(HORIZON,(instant-timedelta(days=67)).isoformat())):
            try:existing.add(json.loads(row["evidence"]).get("isin"))
            except (ValueError,TypeError):continue
        for r in report.get("items",[])[:10]:
            if count>=3:break
            if not m.exact_isin(r.get("isin")) or r["isin"] in existing or r.get("qualified") is not False or r.get("adjustment_verified_for_screen") is not True:continue
            try:
                if not 1<=(today-date.fromisoformat(r["as_of"])).days<=4:continue
                if not m.number(r["close"],.0001,1e9):continue
                lanes=sorted(set(r["strategies"])&set(m.LANES))
                if not lanes:continue
                e={k:r[k] for k in ("symbol","exchange","close","as_of","isin")}
                e.update(methodology=VERSION,adjustment_status="ADJUSTED",strategies=lanes)
                cursor=db.execute("""INSERT OR IGNORE INTO watch_outcomes(instrument_id,horizon,observed_date,published_at,maturity_date,evidence)
                    VALUES(?,?,?,?,?,?)""",(r["id"],HORIZON,r["as_of"],instant.isoformat(),(today+timedelta(days=60)).isoformat(),json.dumps(e,allow_nan=False)))
                count+=cursor.rowcount;existing.add(r["isin"])
            except (ValueError,TypeError,KeyError):continue
    return count

def summary(connect,instant):
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    with closing(connect()) as db:
        watch_outcomes._table(db)
        rows=db.execute("SELECT * FROM watch_outcomes WHERE horizon=? AND published_at>=? ORDER BY published_at LIMIT 5000",(HORIZON,(instant-timedelta(days=366)).isoformat())).fetchall()
    groups={k:{"published":0,"mature":0,"returns":[],"benchmark_differences":[]} for k in m.LANES}
    for row in rows:
        try:
            e=json.loads(row["evidence"])
            if e.get("methodology")!=VERSION or not m.exact_isin(e.get("isin")):continue
            published=rel._stamp(row["published_at"]);maturity=date.fromisoformat(row["maturity_date"])
            if maturity!=published+timedelta(days=60):continue
            mature=today>maturity+timedelta(days=7)
            change=rel._outcome(row,published,maturity,today) if mature else None
            benchmark=rel._index_change(row,change) if change is not None else None
            for lane in set(e.get("strategies",[]))&set(groups):
                g=groups[lane];g["published"]+=1
                if mature:g["mature"]+=1
                if change is not None:
                    g["returns"].append(change*100)
                    if benchmark is not None:g["benchmark_differences"].append((change-benchmark)*100)
        except (ValueError,TypeError,KeyError,OverflowError):continue
    result={}
    for lane,g in groups.items():
        values=g["returns"];comp=g["benchmark_differences"]
        result[lane]={"published":g["published"],"mature":g["mature"],"observed":len(values),
            "mean_observed_price_return_percent":round(mean(values),4) if values else None,
            "matched_price_index_count":len(comp),"mean_difference_vs_price_index_pp":round(mean(comp),4) if comp else None}
    return {"methodology":VERSION,"status":"OBSERVED_OUTCOMES" if any(g["observed"] for g in result.values()) else "AWAITING_MATURITY",
        "lanes":result,"qualified":False,"notice":"Frozen nonoverlapping company publications; 60 calendar days, gross adjusted close-to-close outcomes, not execution or portfolio returns."}
