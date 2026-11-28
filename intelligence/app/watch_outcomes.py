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
from .replay_evidence import exact_isin, full_manifest, corporate_action_status
from .automatic_company_evidence import cached_action_reports
from .corporate_action_normalization import reported_crossings
from .strategy_validation import price_index_history

OUTCOME_EVIDENCE_VERSION = "WATCH-SESSION-EVIDENCE-2"
RISK_PATH_VERSION = "WATCH-CLOSE-PATH-1"
BENCHMARK_VERSION = "WATCH-PRICE-INDEX-1"

HORIZONS = {"SWING": 14, "SHORT_TERM": 60, "LONG_TERM": 180}
IST = ZoneInfo("Asia/Kolkata")


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS watch_outcomes(
        instrument_id INTEGER NOT NULL, horizon TEXT NOT NULL, observed_date TEXT NOT NULL,
        published_at TEXT NOT NULL, maturity_date TEXT NOT NULL, evidence TEXT NOT NULL,
        attempted_at TEXT, status TEXT NOT NULL DEFAULT 'PENDING', outcome TEXT,
        PRIMARY KEY(instrument_id,horizon,observed_date))""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS watch_publication_immutable
        BEFORE UPDATE OF instrument_id,horizon,observed_date,published_at,maturity_date,evidence ON watch_outcomes
        BEGIN SELECT RAISE(ABORT,'immutable watch publication'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS watch_observed_immutable
        BEFORE UPDATE ON watch_outcomes WHEN OLD.status='OBSERVED'
        BEGIN SELECT RAISE(ABORT,'immutable observed outcome'); END""")


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
                        # Freeze score inputs at original publication, never backfill
                        # past rows using a subsequent research snapshot.
                        from . import score_calibration
                        frozen=score_calibration.capture(item,horizon,result,(section.get("result") or {}).get("discovery_coverage") or {},today)
                        if frozen is not None:evidence["score_calibration"]=frozen
                        from . import bracket_research
                        bracket=bracket_research.freeze(item,horizon,result,(section.get("result") or {}).get("discovery_coverage") or {},today)
                        if bracket is not None:evidence["bracket_research"]=bracket
                        if isinstance(item.get("isin"),str) and re.fullmatch(r"IN[A-Z0-9]{10}",item["isin"]):
                            evidence["isin"]=item["isin"]
                        db.execute("""INSERT OR IGNORE INTO watch_outcomes
                            (instrument_id,horizon,observed_date,published_at,maturity_date,evidence)
                            VALUES (?,?,?,?,?,?)""",
                            (instrument,horizon,observed.isoformat(),instant.isoformat(),
                             (today+timedelta(days=days)).isoformat(),json.dumps(evidence,allow_nan=False)))
                    except (ValueError,TypeError,KeyError,OverflowError):
                        continue


def _expected_dates(calendar,exchange,start,maturity,today):
    """First stored regular session after publication and at/after maturity.

    Every intervening calendar date must be known. No substitution of the next
    available candle when the actual expected session observation is missing.
    """
    if (not isinstance(calendar,dict) or calendar.get("exchange")!=exchange
            or calendar.get("through")!=(today-timedelta(days=1)).isoformat()):
        return None
    raw=calendar.get("days")
    if not isinstance(raw,list) or len(raw)>1100:
        return None
    states={}
    for row in raw:
        day=date.fromisoformat(row["trade_date"])
        state=row["state"]
        if day in states or not today-timedelta(days=1100)<=day<today or state not in (
                "REGULAR","CLOSED","UNKNOWN","SPECIAL_SESSION_UNSUPPORTED"):
            return None
        states[day]=state
    expected=[]
    day=start+timedelta(days=1)
    while day<today and day<=maturity+timedelta(days=7):
        state=states.get(day)
        if state not in ("REGULAR","CLOSED"):
            return None
        if state=="REGULAR":
            if not expected and day>start+timedelta(days=7):
                return None
            expected.append(day)
            if day>=maturity:
                return expected
        day+=timedelta(days=1)
    return None


def _risk_path(values):
    """Observed closing marks only; no intraday excursion or executed equity."""
    peak=values[0]
    drawdown=0.0
    for value in values:
        peak=max(peak,value)
        drawdown=min(drawdown,100*(value/peak-1))
    low=100*(min(values)/values[0]-1)
    high=100*(max(values)/values[0]-1)
    if not all(isfinite(v) and -100<=v<=1e6 for v in (drawdown,low,high)):
        return None
    return {"version":RISK_PATH_VERSION,"observations":len(values),
            "worst_close_from_entry_percent":round(low,4),"best_close_from_entry_percent":round(high,4),
            "peak_to_trough_close_drawdown_percent":round(drawdown,4),
            "notice":"Gross observed close marks only; not intraday excursion, portfolio drawdown, executable stop or capital guarantee."}


def _benchmark_path(benchmark,expected,today):
    """Same completed dates and closing marks, not TRI or executable returns."""
    try:
        index=price_index_history(benchmark,today)
        dates=[d.isoformat() for d in expected]
        if len(dates)<2 or sorted(d for d in index if dates[0]<=d<=dates[-1])!=dates:
            return None
        first,last=index[dates[0]][1],index[dates[-1]][1]
        change=100*(last/first-1)
        if not isfinite(change) or not -100<change<=1e6:
            return None
        return {"version":BENCHMARK_VERSION,"benchmark_key":"NSE_INDEX|Nifty 50",
                "kind":"PRICE_INDEX","source_code":"UPSTOX","entry_date":dates[0],"exit_date":dates[-1],
                "observations":len(dates),"entry_close":first,"exit_close":last,
                "gross_return_percent":round(change,4)}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,IndexError):
        return None


def evaluate(row, payload, today, calendar=None, *, action_report=None, instant=None, benchmark=None):
    evidence=json.loads(row["evidence"])
    instrument=payload["instrument"]
    if (type(instrument["id"]) is not int or instrument["id"]!=row["instrument_id"]
            or instrument["symbol"]!=evidence["symbol"] or instrument["exchange"]!=evidence["exchange"]
            or not exact_isin(evidence.get("isin")) or instrument.get("isin")!=evidence["isin"]):
        return "IDENTITY_MISMATCH", None
    publication=datetime.fromisoformat(row["published_at"])
    if publication.tzinfo is None:
        return "EVIDENCE_GAP",None
    start=publication.astimezone(IST).date()
    maturity=date.fromisoformat(row["maturity_date"])
    if row["horizon"] not in (*HORIZONS,"FIP"):
        return "EVIDENCE_GAP",None
    if maturity!=start+timedelta(days=60 if row["horizon"]=="FIP" else HORIZONS[row["horizon"]]):
        return "EVIDENCE_GAP",None
    if today<=maturity:
        return "PENDING", None
    try:
        expected=_expected_dates(calendar,evidence["exchange"],start,maturity,today)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        expected=None
    if not expected:
        return "CALENDAR_EVIDENCE_GAP",None
    rows=[]
    for item in payload["candles"]:
        d=date.fromisoformat(item["trade_date"])
        if start<d<=expected[-1]:
            rows.append((d,item))
    rows.sort(key=lambda x:x[0])
    if [d for d,_ in rows]!=expected:
        return "EVIDENCE_GAP",None
    interval=[x for _,x in rows]
    manifest=full_manifest(interval,today)
    if manifest is None:
        return "EVIDENCE_GAP",None
    action=corporate_action_status(instrument,manifest,require_scope=True,today=today)
    if action!="NO_RECORDED_CROSSING_ACTION":
        return action,None
    if instant is not None and reported_crossings(action_report,evidence["isin"],expected[0],expected[-1],instant):
        return "REPORTED_ACTION_RECONCILIATION_REQUIRED",None
    values=[float(x["close"]) for x in interval]
    if any(not isfinite(v) or v<=0 for v in values):
        return "EVIDENCE_GAP",None
    change=100*(values[-1]/values[0]-1)
    if not isfinite(change):
        return "EVIDENCE_GAP",None
    bracket=None
    if isinstance(evidence.get("bracket_research"),dict):
        from . import bracket_research
        bracket=bracket_research.evaluate_frozen(evidence["bracket_research"],instrument,payload["candles"],expected,calendar,today,action_report,instant)
    return "OBSERVED", {"bracket_research":bracket,"entry_date":expected[0].isoformat(),"exit_date":expected[-1].isoformat(),
        "entry_close":values[0],"exit_close":values[-1],"observed_price_return_pct":round(change,4),
        "source_code":interval[0]["source_code"],"evidence_version":OUTCOME_EVIDENCE_VERSION,
        "observations":len(interval),"history_fingerprint":manifest["digest"],"risk_path":_risk_path(values),
        "price_index_comparison":_benchmark_path(benchmark,expected,today),
        "calendar_status":"STORED_SESSIONS_MATCHED","corporate_action_status":action,
        "action_context_through":instrument["action_context_through"],
        "notice":"Observed adjusted close-to-close change on matching stored sessions; not executed or net of fees. Optional matched Nifty 50 price-index comparison excludes dividends. Corporate-action completeness and point-in-time history are not certified."}


def refresh(snapshot, connect, loader=backend_json, instant=None):
    if not snapshot["enabled"]:
        return
    instant=instant or datetime.now(timezone.utc)
    publish(snapshot,connect,instant)
    today=instant.astimezone(IST).date()
    with closing(connect()) as db, db:
        _table(db)
        due=db.execute("""SELECT * FROM watch_outcomes WHERE maturity_date<?
            AND status IN ('PENDING','EVIDENCE_GAP','CALENDAR_EVIDENCE_GAP','ACTION_CONTEXT_UNAVAILABLE','RECORDED_ACTION_RECONCILIATION_REQUIRED','REPORTED_ACTION_RECONCILIATION_REQUIRED','UNAVAILABLE')
            AND (attempted_at IS NULL OR attempted_at<?)
            ORDER BY attempted_at ASC NULLS FIRST,maturity_date LIMIT 5""",
            (today.isoformat(),(instant-timedelta(days=1)).isoformat())).fetchall()
    calendars={}
    benchmark=None
    benchmark_loaded=False
    for row in due:
        key=(row["instrument_id"],row["horizon"],row["observed_date"])
        try:
            exchange=json.loads(row["evidence"])["exchange"]
            if exchange not in ("NSE","BSE"):
                raise ValueError("INVALID_VENUE")
            if exchange not in calendars:
                try:
                    calendars[exchange]=loader(f"/api/v1/market-data/strategy-calendar?exchange={exchange}")
                except Exception:
                    calendars[exchange]=None
            evidence=json.loads(row["evidence"])
            isin=evidence.get("isin")
            cached=cached_action_reports(connect,[isin],instant)
            payload=loader(f"/api/v1/market-data/instruments/{key[0]}/candles?limit=500")
            status,outcome=evaluate(row,payload,today,calendars[exchange],
                                    action_report=cached.get(isin),instant=instant)
            if status=="OBSERVED":
                # One existing internal stored-index read per bounded pass,
                # only when an actual stock observation can be recorded.
                if not benchmark_loaded:
                    benchmark_loaded=True
                    try:
                        benchmark=loader("/api/v1/market-data/strategy-benchmark")
                    except Exception:
                        benchmark=None
                expected=_expected_dates(calendars[exchange],exchange,
                    datetime.fromisoformat(row["published_at"]).astimezone(IST).date(),
                    date.fromisoformat(row["maturity_date"]),today)
                outcome["price_index_comparison"]=_benchmark_path(benchmark,expected,today)
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
        "notice":"Public technical watch history, not trades or validated strategy performance. New observations require exact identity, adjusted source evidence matching stored sessions and usable recorded corporate-action context; legacy outcomes remain visible but are excluded from current reliability metrics."}
