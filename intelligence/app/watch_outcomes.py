"""Immutable public watch publication records and bounded subsequent price evaluation.

No investment advice, trades, portfolio data or success probabilities.
Only adjusted, source-consistent completed daily prices are eligible.
"""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from math import isfinite
import re

from .market_client import backend_json

HORIZONS = {"SWING": 14, "SHORT_TERM": 60, "LONG_TERM": 180}
IST = ZoneInfo("Asia/Kolkata")


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS watch_outcomes(
        instrument_id INTEGER NOT NULL, horizon TEXT NOT NULL, observed_date TEXT NOT NULL,
        published_at TEXT NOT NULL, maturity_date TEXT NOT NULL, evidence TEXT NOT NULL,
        attempted_at TEXT, status TEXT NOT NULL DEFAULT 'PENDING', outcome TEXT,
        PRIMARY KEY(instrument_id,horizon,observed_date))""")


def publish(snapshot, connect, instant):
    if not snapshot["enabled"]:
        return
    today = instant.astimezone(IST).date()
    with closing(connect()) as db, db:
        _table(db)
        for section in snapshot["sections"]:
            if section["status"]!="READY" or section["section"] not in ("NSE","BSE"):
                continue
            for horizon, days in HORIZONS.items():
                result = (section.get("result") or {}).get("horizons",{}).get(horizon,{})
                for item in result.get("candidates",[])[:5]:
                    try:
                        observed = date.fromisoformat(item["as_of"])
                        price = float(item["close"])
                        instrument = int(item["id"])
                        if not 0<=(today-observed).days<=4 or not isfinite(price) or price<=0 or instrument<=0:
                            continue
                        if item["exchange"]!=section["section"] or not re.fullmatch(r"[A-Z0-9._&-]{1,40}",item["symbol"]):
                            continue
                        # Keep the original publication, not a later edited candidate.
                        evidence = {k:item[k] for k in ("symbol","exchange","close","adjustment_status","as_of")}
                        evidence["methodology"] = result.get("methodology","UNKNOWN")
                        if isinstance(item.get("isin"),str) and re.fullmatch(r"IN[A-Z0-9]{10}",item["isin"]):
                            evidence["isin"]=item["isin"]
                        db.execute("""INSERT OR IGNORE INTO watch_outcomes
                            (instrument_id,horizon,observed_date,published_at,maturity_date,evidence)
                            VALUES (?,?,?,?,?,?)""",
                            (instrument,horizon,observed.isoformat(),instant.isoformat(),
                             (today+timedelta(days=days)).isoformat(),json.dumps(evidence,allow_nan=False)))
                    except (ValueError,TypeError,KeyError,OverflowError):
                        continue


def evaluate(row, payload, today):
    evidence=json.loads(row["evidence"])
    instrument=payload["instrument"]
    if (int(instrument["id"])!=row["instrument_id"] or instrument["symbol"]!=evidence["symbol"]
            or instrument["exchange"]!=evidence["exchange"]):
        return "IDENTITY_MISMATCH", None
    if evidence.get("isin") and instrument.get("isin")!=evidence["isin"]:
        return "IDENTITY_MISMATCH", None
    start=datetime.fromisoformat(row["published_at"]).astimezone(IST).date()
    maturity=date.fromisoformat(row["maturity_date"])
    if today<=maturity:
        return "PENDING", None
    rows=[]
    for item in payload["candles"]:
        d=date.fromisoformat(item["trade_date"])
        if start<d<today and d<=maturity+timedelta(days=7):
            rows.append((d,item))
    rows.sort(key=lambda x:x[0])
    if len({d for d,_ in rows})!=len(rows):
        return "EVIDENCE_GAP",None
    entry=next(((d,x) for d,x in rows if d<=start+timedelta(days=7)),None)
    exit_point=next(((d,x) for d,x in rows if d>=maturity),None)
    if not entry or not exit_point:
        return "EVIDENCE_GAP",None
    interval=[x for d,x in rows if entry[0]<=d<=exit_point[0]]
    dates=[d for d,_ in rows if entry[0]<=d<=exit_point[0]]
    sources={x.get("source_code") for x in interval}
    if (any(x.get("adjustment_status")!="ADJUSTED" or x.get("quality_status")!="PROVIDER_VALIDATED" for x in interval)
            or len(sources)!=1 or None in sources or "" in sources
            or any((b-a).days>7 for a,b in zip(dates,dates[1:]))):
        return "EVIDENCE_GAP",None
    values=[float(x["close"]) for x in interval]
    if any(not isfinite(v) or v<=0 for v in values):
        return "EVIDENCE_GAP",None
    return "OBSERVED", {"entry_date":entry[0].isoformat(),"exit_date":exit_point[0].isoformat(),
        "entry_close":values[0],"exit_close":values[-1],"observed_price_return_pct":round(100*(values[-1]/values[0]-1),4),
        "source_code":next(iter(sources)),
        "notice":"Observed adjusted close-to-close change only; not executed, benchmarked, or net of fees."}


def refresh(snapshot, connect, loader=backend_json, instant=None):
    if not snapshot["enabled"]:
        return
    instant=instant or datetime.now(timezone.utc)
    publish(snapshot,connect,instant)
    today=instant.astimezone(IST).date()
    with closing(connect()) as db, db:
        _table(db)
        due=db.execute("""SELECT * FROM watch_outcomes WHERE maturity_date<?
            AND status IN ('PENDING','EVIDENCE_GAP','UNAVAILABLE')
            AND (attempted_at IS NULL OR attempted_at<?)
            ORDER BY attempted_at ASC NULLS FIRST,maturity_date LIMIT 5""",
            (today.isoformat(),(instant-timedelta(days=1)).isoformat())).fetchall()
    for row in due:
        key=(row["instrument_id"],row["horizon"],row["observed_date"])
        try:
            status,outcome=evaluate(row,loader(f"/api/v1/market-data/instruments/{key[0]}/candles?limit=500"),today)
        except Exception:
            status,outcome="UNAVAILABLE",None
        with closing(connect()) as db, db:
            db.execute("""UPDATE watch_outcomes SET attempted_at=?,status=?,outcome=?
                WHERE instrument_id=? AND horizon=? AND observed_date=? AND status!='OBSERVED'""",
                (instant.isoformat(),status,json.dumps(outcome,allow_nan=False) if outcome else None,*key))


def summary(connect, horizon):
    if horizon not in HORIZONS:
        raise ValueError("INVALID_HORIZON")
    with closing(connect()) as db:
        _table(db)
        counts={row[0]:row[1] for row in db.execute("SELECT status,count(*) FROM watch_outcomes WHERE horizon=? GROUP BY status",(horizon,))}
        rows=db.execute("SELECT * FROM watch_outcomes WHERE horizon=? ORDER BY published_at DESC,instrument_id LIMIT 20",(horizon,)).fetchall()
    return {"horizon":horizon,"counts":counts,"items":[{"symbol":json.loads(r["evidence"])["symbol"],
        "exchange":json.loads(r["evidence"])["exchange"],"observed_date":r["observed_date"],
        "published_at":r["published_at"],"maturity_date":r["maturity_date"],"status":r["status"],
        "outcome":json.loads(r["outcome"]) if r["outcome"] else None} for r in rows],
        "notice":"Public technical watch history, not trades or validated strategy performance. Raw or insufficient history is excluded from outcome calculations."}
