"""Calendar-aware triggers for the durable local coordinator.

Only explicit stored session bounds authorize phase-specific triggers. Regular
background research remains independent of calendar availability. This module
does not certify a live feed, ingest candles, or manufacture a trading calendar.
"""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json

from .market_client import backend_json

IST=ZoneInfo("Asia/Kolkata")
POLL_SECONDS=60
MAX_AGE=180
EXCHANGES=("NSE","BSE")
TIMED=("BEFORE_PRE_MARKET","PRE_MARKET","MARKET_HOURS","POST_MARKET")
UNTIMED=("CLOSED","CALENDAR_UNVERIFIED","SPECIAL_SESSION_UNSUPPORTED")
TRIGGERS={
    "PRE_MARKET":("PORTFOLIO_REVIEW","COMPANY_NEWS","COMPANY_EVIDENCE","AI_REVIEW"),
    "MARKET_HOURS":("PORTFOLIO_REVIEW","COMPANY_NEWS"),
    "POST_MARKET":("PORTFOLIO_REVIEW","INSTITUTIONAL_FLOWS","COMPANY_NEWS","WATCH_OUTCOMES","STRATEGY_REPLAY","AI_REVIEW"),
}


def _instant(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_CALENDAR_TIMESTAMP")
    stamp=datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("INVALID_CALENDAR_TIMESTAMP")
    return stamp.astimezone(timezone.utc)


def _phase(observed,opening,closing):
    if observed<opening-timedelta(minutes=90):
        return "BEFORE_PRE_MARKET"
    if observed<opening:
        return "PRE_MARKET"
    if observed<closing:
        return "MARKET_HOURS"
    return "POST_MARKET"


def normalize(payload,instant):
    observed=_instant(payload.get("observed_at"))
    if payload.get("timezone")!="Asia/Kolkata" or not -5<=(instant-observed).total_seconds()<=MAX_AGE:
        raise ValueError("STALE_OR_INVALID_CALENDAR_CONTEXT")
    today=instant.astimezone(IST).date().isoformat()
    if observed.astimezone(IST).date().isoformat()!=today:
        raise ValueError("CALENDAR_DATE_MISMATCH")
    raw=payload.get("sessions")
    if not isinstance(raw,list) or len(raw)!=2:
        raise ValueError("INVALID_CALENDAR_SESSIONS")
    rows={}
    for row in raw:
        exchange,phase=row.get("exchange"),row.get("phase")
        if exchange not in EXCHANGES or exchange in rows or row.get("session_date")!=today:
            raise ValueError("INVALID_CALENDAR_IDENTITY")
        opening,closing=row.get("open_at"),row.get("close_at")
        if phase in TIMED:
            start,end=_instant(opening),_instant(closing)
            if not start<end or any(t.astimezone(IST).date().isoformat()!=today for t in (start,end)):
                raise ValueError("INVALID_CALENDAR_BOUNDS")
            if _phase(observed,start,end)!=phase or _phase(instant,start,end)!=phase:
                raise ValueError("CALENDAR_PHASE_CHANGED")
            opening,closing=start.isoformat(),end.isoformat()
        elif phase not in UNTIMED or opening is not None or closing is not None:
            raise ValueError("INVALID_CALENDAR_PHASE")
        rows[exchange]={"exchange":exchange,"session_date":today,"phase":phase,
                        "open_at":opening,"close_at":closing}
    return {"observed_at":observed.isoformat(),"timezone":"Asia/Kolkata",
            "sessions":[rows[e] for e in EXCHANGES]}


def _tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS research_calendar_context(
      id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, observed_at REAL NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS research_session_triggers(
      exchange TEXT NOT NULL, session_date TEXT NOT NULL, phase TEXT NOT NULL,
      observed_at REAL NOT NULL, PRIMARY KEY(exchange,session_date,phase))""")


def refresh(connect,loader=backend_json,instant=None):
    payload=loader("/api/v1/market-data/session-context")
    instant=instant or datetime.now(timezone.utc)
    normalized=normalize(payload,instant)
    observed=_instant(normalized["observed_at"]).timestamp()
    now=instant.timestamp()
    with closing(connect()) as db,db:
        _tables(db)
        db.execute("BEGIN IMMEDIATE")
        old=db.execute("SELECT observed_at FROM research_calendar_context WHERE id=1").fetchone()
        if old and old["observed_at"]>observed:
            raise ValueError("OUT_OF_ORDER_CALENDAR")
        db.execute("""INSERT INTO research_calendar_context VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,observed_at=excluded.observed_at""",
            (json.dumps(normalized,allow_nan=False),observed))
        # Per-venue/date/phase dedupe survives restarts. A transition only
        # advances completed jobs; never clears failure backoff or a claim.
        due=set()
        for row in normalized["sessions"]:
            phase=row["phase"]
            if phase not in TRIGGERS:
                continue
            inserted=db.execute("""INSERT OR IGNORE INTO research_session_triggers VALUES(?,?,?,?)""",
                                (row["exchange"],row["session_date"],phase,observed))
            if inserted.rowcount==1:
                due.add("SECTION:"+row["exchange"])
                due.update(TRIGGERS[phase])
        for job in due:
            db.execute("""UPDATE research_job_state SET next_due=min(next_due,?)
                          WHERE job=? AND status='PASS_COMPLETED'""",(now,job))
        db.execute("DELETE FROM research_session_triggers WHERE session_date<?",
                   ((instant.astimezone(IST).date()-timedelta(days=7)).isoformat(),))
    return normalized


def read(connect,instant=None):
    instant=instant or datetime.now(timezone.utc)
    try:
        with closing(connect()) as db:
            _tables(db)
            row=db.execute("SELECT payload FROM research_calendar_context WHERE id=1").fetchone()
            if row:
                value=normalize(json.loads(row["payload"]),instant)
                return {"status":"STORED_SESSION_CONTEXT",**value,
                        "notice":"Stored regular-session schedule, not a live exchange status or feed confirmation. Daily discovery continues to use prior completed days."}
    except (ValueError,TypeError,AttributeError,KeyError,OverflowError):
        pass
    return {"status":"CALENDAR_UNAVAILABLE_OR_STALE","sessions":[],
            "notice":"No current calendar phase can be asserted; ordinary research remains independent."}
