"""Bounded immutable history of public market research reminders.

Only existing market-risk observations enter this local ledger. Upcoming
calendar reminders stay current-only: a past schedule is not a release.
"""
from contextlib import closing
from datetime import timedelta
import json
from . import public_research_alerts

RETENTION=timedelta(days=7)
LIMIT=100
SOURCES=("ATLAS local price-volume research","ATLAS local breakout research")

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS public_market_alert_history(
        id TEXT PRIMARY KEY, first_recorded REAL NOT NULL, payload TEXT NOT NULL)""")

def _validated(row):
    from .notifications import ResearchAlert
    item=ResearchAlert.model_validate(row)
    if (item.category!="RISK_WARNING" or item.source_name not in SOURCES
            or item.source_url is not None or not item.id.startswith("research-")
            or item.event_date is None):
        raise ValueError("INVALID_PUBLIC_MARKET_ALERT")
    return item

def refresh(connect,snapshot,instant):
    if snapshot.get("enabled") is not True:
        return
    rows=[_validated(row) for row in public_research_alerts.market_alerts(snapshot,instant)]
    stamp=instant.timestamp()
    with closing(connect()) as db,db:
        _table(db)
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM public_market_alert_history WHERE first_recorded<?",(stamp-RETENTION.total_seconds(),))
        for item in rows:
            db.execute("""INSERT INTO public_market_alert_history(id,first_recorded,payload)
                VALUES(?,?,?) ON CONFLICT(id) DO NOTHING""",
                (item.id,stamp,item.model_dump_json()))
        db.execute("""DELETE FROM public_market_alert_history WHERE id IN (
            SELECT id FROM public_market_alert_history
            ORDER BY first_recorded DESC,id LIMIT -1 OFFSET ?)""",(LIMIT,))

def read(connect,instant):
    """Read retained historical observations, never assert current relevance."""
    stamp=instant.timestamp()
    with closing(connect()) as db:
        # Read path does not create or mutate the alert ledger.
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='public_market_alert_history'").fetchone():
            return []
        rows=db.execute("""SELECT id,payload FROM public_market_alert_history
            WHERE first_recorded BETWEEN ? AND ?
            ORDER BY first_recorded DESC,id LIMIT ?""",
            (stamp-RETENTION.total_seconds(),stamp,LIMIT)).fetchall()
    result=[]
    for row in rows:
        item=_validated(json.loads(row["payload"]))
        if item.id!=row["id"] or item.published_at>instant:
            raise ValueError("INVALID_PUBLIC_ALERT_HISTORY")
        result.append(item)
    return result
