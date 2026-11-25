"""Authorized aggregate cash-flow observations, isolated from manual ledger and holdings."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
import json
import os

from .p1_research import institutional_activity

IST = ZoneInfo("Asia/Kolkata")
PARTICIPANTS = ("FII", "DII")
SCOPE = "NSE_CASH"
UNIT = "PROVIDER_REPORTED"
SESSION_WINDOWS=(1,5,10,20,60,120,250)
RETENTION_DAYS=400
SESSION_NOTICE=("Prior IST dates matched against locally stored NSE regular sessions and closures. "
    "Each included amount was retrieved after its observation date; this does not certify final or official flow totals. "
    "Unknown/special sessions and missing participant data withhold the affected window. No current-day data or stock-level attribution.")
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


def _calendar_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS institutional_session_calendar(
        id INTEGER PRIMARY KEY CHECK(id=1), captured_at TEXT NOT NULL, payload TEXT NOT NULL)""")


def _calendar_states(calendar,today):
    through=today-timedelta(days=1)
    if not isinstance(calendar,dict) or calendar.get("exchange")!="NSE" or calendar.get("through")!=through.isoformat():
        raise ValueError("CALENDAR_SCOPE_MISMATCH")
    rows=calendar.get("days")
    if not isinstance(rows,list) or not 1<=len(rows)<=1100:
        raise ValueError("CALENDAR_ROWS_INVALID")
    states={}
    for row in rows:
        day=date.fromisoformat(row["trade_date"])
        state=row["state"]
        if day in states or not today-timedelta(days=1100)<=day<=through or state not in ("REGULAR","CLOSED","UNKNOWN","SPECIAL_SESSION_UNSUPPORTED"):
            raise ValueError("CALENDAR_ROW_INVALID")
        states[day]=state
    return states


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


def refresh(connect, loader=institutional_activity, instant=None, *, calendar_loader=None):
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
    calendar=None
    if calendar_loader is not None:
        try:
            candidate=calendar_loader("/api/v1/market-data/strategy-calendar?exchange=NSE")
            states=_calendar_states(candidate,instant.astimezone(IST).date())
            calendar={"exchange":"NSE","through":candidate["through"],"days":[{"trade_date":d.isoformat(),"state":s} for d,s in sorted(states.items())]}
        except Exception:
            pass
    with closing(connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT count(*) FROM automatic_institutional_state WHERE attempted_at=? AND status='RUNNING'",(stamp,)).fetchone()[0]!=2:
            return
        _calendar_table(db)
        if calendar is not None:
            db.execute("INSERT INTO institutional_session_calendar VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload",(stamp,json.dumps(calendar)))
        else:
            db.execute("DELETE FROM institutional_session_calendar")
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
                    WHERE excluded.observed_at>automatic_institutional_history.observed_at
                       OR (excluded.observed_at=automatic_institutional_history.observed_at
                           AND excluded.buy_amount=automatic_institutional_history.buy_amount
                           AND excluded.sell_amount=automatic_institutional_history.sell_amount
                           AND excluded.retrieved_at>automatic_institutional_history.retrieved_at)""",
                    (participant,row["trade_date"],row["observed_at"],stamp,row["buy_amount"],row["sell_amount"]))
            db.execute("""UPDATE automatic_institutional_state SET status=?,payload=?,next_attempt_at=?
                WHERE participant=? AND attempted_at=?""",
                (status,json.dumps({"latest_date":latest}), (instant+timedelta(hours=1)).isoformat(),participant,stamp))
        db.execute("DELETE FROM automatic_institutional_history WHERE trade_date<?",
                   ((instant.astimezone(IST).date()-timedelta(days=RETENTION_DAYS)).isoformat(),))


def _flow_window(fii,dii,dates,today):
    count=len(dates)
    participants={}
    directions={}
    for key,source in (("FII",fii),("DII",dii)):
        amounts=[]
        for day in dates:
            row=source[day]
            if _stamp(row["observed_at"]).astimezone(IST).date().isoformat()!=day:
                raise ValueError("OBSERVATION_DATE_MISMATCH")
            buy,sell=_amount(row["buy_amount"]),_amount(row["sell_amount"])
            net=buy-sell
            if Decimal(row["net_amount"])!=net:
                raise ValueError("NET_AMOUNT_MISMATCH")
            amounts.append((buy,sell,net))
        gross=sum((a+b for a,b,_ in amounts),Decimal(0))
        net=sum((n for _,_,n in amounts),Decimal(0))
        signs=[1 if n>0 else -1 if n<0 else 0 for _,_,n in amounts]
        directions[key]=signs
        positive,negative=signs.count(1),signs.count(-1)
        # Agreement between aggregate direction and majority date
        # direction, not a prediction or market-regime classification.
        persistence=("NET_BUYING_MAJORITY" if net>0 and positive>count/2
            else "NET_SELLING_MAJORITY" if net<0 and negative>count/2
            else "MIXED_OR_BALANCED")
        participants[key]={"net_amount":str(net),"gross_amount":str(gross),
            "net_to_gross_percent":float(round(100*net/gross,4)) if gross>0 else None,
            "net_buying_dates":positive,"net_selling_dates":negative,
            "balanced_dates":signs.count(0),"direction_consistency":persistence}
    pairs=list(zip(directions["FII"],directions["DII"]))
    return {"observation_count":count,"dates":dates,
        "participants":participants,
        "both_buying_dates":sum(a==b==1 for a,b in pairs),
        "both_selling_dates":sum(a==b==-1 for a,b in pairs),
        "fii_selling_dii_buying_dates":sum(a==-1 and b==1 for a,b in pairs),
        "fii_buying_dii_selling_dates":sum(a==1 and b==-1 for a,b in pairs),
        "one_or_both_balanced_dates":sum(a==0 or b==0 for a,b in pairs),
        "latest_date_is_today":dates[0]==today.isoformat()}


def _session_context(calendar,records,today,instant):
    result={"status":"CALENDAR_UNAVAILABLE","windows":[],"notice":SESSION_NOTICE}
    try:
        states=_calendar_states(calendar,today)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return result
    expected=[]
    stop="HISTORY_RETENTION_LIMIT"
    unresolved=None
    for offset in range(1,RETENTION_DAYS+1):
        day=today-timedelta(days=offset)
        state=states.get(day,"UNKNOWN")
        if state not in ("REGULAR","CLOSED"):
            stop="CALENDAR_INCOMPLETE"
            unresolved=day.isoformat()
            break
        if state=="REGULAR":
            expected.append(day.isoformat())
            if len(expected)==max(SESSION_WINDOWS):
                break
    for count in SESSION_WINDOWS:
        dates=expected[:count]
        row={"session_count":count,"status":"UNAVAILABLE","latest_session":dates[0] if dates else None,
             "first_session":dates[-1] if len(dates)==count else None,"missing_count":None,"missing_dates":[],"metrics":None}
        if len(dates)!=count:
            row["status"]=stop
            row["unresolved_calendar_date"]=unresolved
        else:
            missing=[]
            for day in dates:
                for key in PARTICIPANTS:
                    try:
                        item=records[key][day]
                        retrieved=_stamp(item["retrieved_at"])
                        observed=_stamp(item["observed_at"])
                        if not observed<=retrieved<=instant or retrieved.astimezone(IST).date()<=date.fromisoformat(day):
                            raise ValueError("NOT_RECONFIRMED_ON_LATER_DATE")
                        if observed.astimezone(IST).date().isoformat()!=day or _amount(item["buy_amount"])-_amount(item["sell_amount"])!=Decimal(item["net_amount"]):
                            raise ValueError("INVALID_OBSERVATION")
                    except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError):
                        missing.append(day)
                        break
            row["missing_count"]=len(missing)
            row["missing_dates"]=missing[:10]
            if missing:
                row["status"]="MISSING_OR_UNCONFIRMED_SESSION_FLOWS"
            else:
                row["metrics"]=_flow_window(records["FII"],records["DII"],dates,today)
                row["status"]="STORED_REGULAR_SESSIONS_MATCHED"
        result["windows"].append(row)
    result["status"]="SESSION_WINDOWS_AVAILABLE" if any(r["metrics"] for r in result["windows"]) else "SESSION_EVIDENCE_INCOMPLETE"
    return result


def _paired_context(fii,dii,today):
    """Use matched provider observation dates, never assumed consecutive sessions.

    Net/gross ratios are dimensionless within each participant; do not combine
    participant amounts or infer market-wide buying pressure from the ratio.
    """
    windows=[]
    common=sorted(fii.keys() & dii.keys(),reverse=True)
    if not common or common[0]!=max(fii) or common[0]!=max(dii):
        return {"status":"INSUFFICIENT_MATCHED_DATES","windows":[],"notice":NOTICE}
    for count,max_age in ((5,14),(20,45)):
        dates=common[:count]
        if len(dates)!=count:
            continue
        try:
            ages=[(today-datetime.fromisoformat(day).date()).days for day in dates]
            if min(ages)<0 or max(ages)>max_age or ages[0]>4:
                continue
            windows.append(_flow_window(fii,dii,dates,today))
        except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError):
            continue
    return {"status":"MATCHED_PROVIDER_DATES_ONLY" if windows else "INSUFFICIENT_MATCHED_DATES",
        "windows":windows,"notice":"Matched reported dates only, not consecutive or verified completed trading sessions. Net/gross is net amount divided by total reported buying plus selling within each participant. Today's observation may be partial. Opposing flows do not establish direct counterparties, market support, price impact or future direction."}


def read(connect, instant=None):
    instant = instant or datetime.now(timezone.utc)
    base = {"status":"DISABLED_OR_NOT_AUTHORIZED","market":SCOPE,"unit":UNIT,
            "participants":{},"paired_five_date_window":None,
            "flow_context":{"status":"UNAVAILABLE","windows":[],"notice":NOTICE},
            "session_flow_context":{"status":"UNAVAILABLE","windows":[],"notice":SESSION_NOTICE},
            "blockers":["AUTHORIZED_BULK_BLOCK_DEAL_FEED_MISSING","STOCK_LEVEL_INSTITUTIONAL_TRADES_UNVERIFIED","RETAIL_FLOW_FEED_MISSING"],
            "notice":NOTICE}
    if not permitted():
        return base
    base["status"] = "AWAITING_RECENT_EVIDENCE"
    today = instant.astimezone(IST).date()
    historical={key:{} for key in PARTICIPANTS}
    calendar=None
    with closing(connect()) as db:
        _table(db)
        _calendar_table(db)
        cached=db.execute("SELECT captured_at,payload FROM institutional_session_calendar WHERE id=1").fetchone()
        if cached and timedelta(0)<=instant-_stamp(cached["captured_at"])<=timedelta(hours=2):
            calendar=json.loads(cached["payload"])
        for participant in PARTICIPANTS:
            state = db.execute("SELECT * FROM automatic_institutional_state WHERE participant=?", (participant,)).fetchone()
            section = {"status":state["status"] if state else "PENDING","retrieved_at":state["attempted_at"] if state else None,
                       "endpoint":"/v2/market/"+participant.lower(),"records":[]}
            if state and state["status"]=="RECENT" and timedelta(0)<=instant-_stamp(state["attempted_at"])<=timedelta(hours=2):
                latest = json.loads(state["payload"])["latest_date"]
                if latest and 0<=(today-datetime.fromisoformat(latest).date()).days<=4:
                    session_rows=db.execute("""SELECT * FROM automatic_institutional_history
                        WHERE participant=? AND trade_date<=? AND trade_date>=? ORDER BY trade_date DESC LIMIT 400""",
                        (participant,latest,(today-timedelta(days=RETENTION_DAYS)).isoformat())).fetchall()
                    for row in session_rows:
                        buy,sell=Decimal(row["buy_amount"]),Decimal(row["sell_amount"])
                        historical[participant][row["trade_date"]]={"observed_at":row["observed_at"],"retrieved_at":row["retrieved_at"],
                            "buy_amount":str(buy),"sell_amount":str(sell),"net_amount":str(buy-sell)}
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
    base["flow_context"]=_paired_context(fii,dii,today)
    base["session_flow_context"]=_session_context(calendar,historical,today,instant)
    active=sum(bool(s["records"]) for s in base["participants"].values())
    base["status"]="RECENT_PROVIDER_EVIDENCE" if active==2 else "PARTIAL_PROVIDER_EVIDENCE" if active else "AWAITING_RECENT_EVIDENCE"
    return base
