"""Authorized aggregate cash-flow observations, isolated from manual ledger and holdings."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import json
import os

from .p1_research import institutional_activity

IST = ZoneInfo("Asia/Kolkata")
PARTICIPANTS = ("FII", "DII")
SCOPE = "NSE_CASH"
UNIT = "PROVIDER_REPORTED"
NOTICE = ("Aggregate provider-reported NSE cash activity, not stock-specific transactions. "
          "Units remain provider-reported; no assumed rupee/crore conversion. "
          "Recent records may be provisional. Five reported dates are not necessarily consecutive sessions.")


def permitted():
    return (os.getenv("ATLAS_AUTOMATIC_INSTITUTIONAL_ENABLED", "false").lower() == "true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED", "false").lower() == "true"
            and os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED", "false").lower() == "true"
            and bool(os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()))


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_institutional_state(
        participant TEXT PRIMARY KEY, attempted_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL,
        status TEXT NOT NULL, payload TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_institutional_history(
        participant TEXT NOT NULL, trade_date TEXT NOT NULL, observed_at TEXT NOT NULL,
        retrieved_at TEXT NOT NULL, buy_amount TEXT NOT NULL, sell_amount TEXT NOT NULL,
        PRIMARY KEY(participant,trade_date))""")


def _amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("INVALID_AMOUNT")
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal("1e18"):
            raise ValueError("INVALID_AMOUNT")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("INVALID_AMOUNT") from exc


def _stamp(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_TIMESTAMP")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("INVALID_TIMESTAMP")
    return result.astimezone(timezone.utc)


def normalize(report, participant, instant):
    if (report.get("market") != SCOPE or report.get("interval") != "1D"
            or report.get("unit") != UNIT):
        return []
    section = report.get("participants", {}).get(participant.lower(), {})
    if section.get("status") != "AVAILABLE" or not isinstance(section.get("data"), list):
        return []
    by_date = {}
    conflicts = set()
    for row in section["data"][:250]:
        try:
            stamp = _stamp(row["observed_at"])
            if stamp > instant or instant - stamp > timedelta(days=120):
                continue
            day = stamp.astimezone(IST).date().isoformat()
            buy, sell = _amount(row["buy_amount"]), _amount(row["sell_amount"])
            values = (buy, sell)
            previous = by_date.get(day)
            if previous and previous[0] == stamp and previous[1] != values:
                conflicts.add(day)
            if previous is None or stamp > previous[0]:
                by_date[day] = (stamp, values)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return [{"trade_date": day, "observed_at": stamp.isoformat(),
             "buy_amount": str(values[0]), "sell_amount": str(values[1])}
            for day, (stamp, values) in sorted(by_date.items()) if day not in conflicts]


def refresh(connect, loader=institutional_activity, instant=None):
    if not permitted():
        return
    instant = instant or datetime.now(timezone.utc)
    stamp = instant.isoformat()
    with closing(connect()) as db, db:
        _table(db)
        # Serialize the shared two-endpoint request across restarts/workers.
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM automatic_institutional_state WHERE next_attempt_at>? LIMIT 1", (stamp,)).fetchone():
            return
        for participant in PARTICIPANTS:
            db.execute("""INSERT INTO automatic_institutional_state VALUES(?,?,?,'RUNNING',NULL)
                ON CONFLICT(participant) DO UPDATE SET attempted_at=excluded.attempted_at,
                next_attempt_at=excluded.next_attempt_at,status='RUNNING',payload=NULL""",
                (participant, stamp, (instant+timedelta(hours=1)).isoformat()))
    try:
        report = loader("1D")
    except Exception:
        report = {}
    with closing(connect()) as db, db:
        for participant in PARTICIPANTS:
            try:
                rows = normalize(report, participant, instant)
            except (AttributeError, TypeError, ValueError):
                rows = []
            latest = rows[-1]["trade_date"] if rows else None
            status = "RECENT" if latest and (instant.astimezone(IST).date()-datetime.fromisoformat(latest).date()).days <= 4 else "STALE" if rows else "UNAVAILABLE"
            for row in rows:
                # Newer provider observations can revise a provisional date.
                # Same-timestamp conflicts never overwrite the existing record.
                db.execute("""INSERT INTO automatic_institutional_history VALUES(?,?,?,?,?,?)
                    ON CONFLICT(participant,trade_date) DO UPDATE SET observed_at=excluded.observed_at,
                    retrieved_at=excluded.retrieved_at,buy_amount=excluded.buy_amount,sell_amount=excluded.sell_amount
                    WHERE excluded.observed_at>automatic_institutional_history.observed_at""",
                    (participant,row["trade_date"],row["observed_at"],stamp,row["buy_amount"],row["sell_amount"]))
            db.execute("""UPDATE automatic_institutional_state SET status=?,payload=?,next_attempt_at=?
                WHERE participant=? AND attempted_at=?""",
                (status,json.dumps({"latest_date":latest}), (instant+timedelta(hours=1)).isoformat(),participant,stamp))
        db.execute("DELETE FROM automatic_institutional_history WHERE trade_date<?",
                   ((instant.astimezone(IST).date()-timedelta(days=120)).isoformat(),))


def read(connect, instant=None):
    instant = instant or datetime.now(timezone.utc)
    base = {"status":"DISABLED_OR_NOT_AUTHORIZED","market":SCOPE,"unit":UNIT,
            "participants":{},"paired_five_date_window":None,
            "blockers":["AUTHORIZED_BULK_BLOCK_DEAL_FEED_MISSING","STOCK_LEVEL_INSTITUTIONAL_TRADES_UNVERIFIED","RETAIL_FLOW_FEED_MISSING"],
            "notice":NOTICE}
    if not permitted():
        return base
    base["status"] = "AWAITING_RECENT_EVIDENCE"
    today = instant.astimezone(IST).date()
    with closing(connect()) as db:
        _table(db)
        for participant in PARTICIPANTS:
            state = db.execute("SELECT * FROM automatic_institutional_state WHERE participant=?", (participant,)).fetchone()
            section = {"status":state["status"] if state else "PENDING","retrieved_at":state["attempted_at"] if state else None,
                       "endpoint":"/v2/market/"+participant.lower(),"records":[]}
            if state and state["status"]=="RECENT" and timedelta(0)<=instant-_stamp(state["attempted_at"])<=timedelta(hours=2):
                latest = json.loads(state["payload"])["latest_date"]
                if latest and 0<=(today-datetime.fromisoformat(latest).date()).days<=4:
                    records = db.execute("""SELECT * FROM automatic_institutional_history
                        WHERE participant=? AND trade_date<=? AND trade_date>=?
                        ORDER BY trade_date DESC LIMIT 20""", (participant,latest,(today-timedelta(days=45)).isoformat())).fetchall()
                    for row in records:
                        buy,sell=Decimal(row["buy_amount"]),Decimal(row["sell_amount"])
                        section["records"].append({"trade_date":row["trade_date"],"observed_at":row["observed_at"],
                            "buy_amount":str(buy),"sell_amount":str(sell),"net_amount":str(buy-sell)})
            if not section["records"] and section["status"]=="RECENT":
                section["status"]="STALE"
            base["participants"][participant]=section
    fii={r["trade_date"]:r for r in base["participants"]["FII"]["records"]}
    dii={r["trade_date"]:r for r in base["participants"]["DII"]["records"]}
    common=sorted(fii.keys() & dii.keys(), reverse=True)[:5]
    # Require latest participant dates to match, and at least five recent pairs.
    if len(common)==5 and common[0]==max(fii)==max(dii) and (today-datetime.fromisoformat(common[-1]).date()).days<=14:
        base["paired_five_date_window"]={"dates":common,
            "fii_net":str(sum((Decimal(fii[d]["net_amount"]) for d in common),Decimal(0))),
            "dii_net":str(sum((Decimal(dii[d]["net_amount"]) for d in common),Decimal(0)))}
    active=sum(bool(s["records"]) for s in base["participants"].values())
    base["status"]="RECENT_PROVIDER_EVIDENCE" if active==2 else "PARTIAL_PROVIDER_EVIDENCE" if active else "AWAITING_RECENT_EVIDENCE"
    return base
