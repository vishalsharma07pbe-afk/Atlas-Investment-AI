"""Restricted official BLS iCalendar subscription, no inferred release results."""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from zoneinfo import ZoneInfo
import json
import os
import re

from .global_macro import _download

INTERVAL=21600
URL="https://www.bls.gov/schedule/news_release/bls.ics"
SOURCE_PAGE="https://www.bls.gov/help/hlpiCAL.htm"
MAX_BYTES=1_000_000
EASTERN=ZoneInfo("America/New_York")
NOTICE=("Official BLS schedule only; times may change. Covers supported US economic releases in the next 30 days and preceding 48 hours. "
        "A passed scheduled time does not confirm publication, numerical results or market impact. "
        "Upcoming within 24 hours is a research reminder, not a forecast or trade instruction. "
        "Central bank decisions and other countries require separate sources.")
TOPICS=(
    ("INFLATION",r"\b(?:consumer price index|producer price index|import and export price indexes)\b"),
    ("EMPLOYMENT",r"\b(?:employment situation|job openings and labor turnover|employment cost index|state employment and unemployment)\b"),
    ("PRODUCTIVITY",r"\bproductivity and costs\b"),
)

def permitted():
    return (os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and os.getenv("ATLAS_ECONOMIC_CALENDAR_ENABLED","false").lower()=="true")

def empty(status):
    return {"status":status,"source":"US Bureau of Labor Statistics","source_url":SOURCE_PAGE,"events":[],"notice":NOTICE}

def _lines(payload):
    if len(payload)>MAX_BYTES:
        raise ValueError("CALENDAR_BYTE_LIMIT")
    raw=payload.decode("utf-8-sig")
    if "\x00" in raw:
        raise ValueError("CALENDAR_INVALID")
    lines=[]
    for line in raw.splitlines():
        if line.startswith((" ","\t")):
            if not lines:
                raise ValueError("CALENDAR_FOLD_INVALID")
            lines[-1]+=line[1:]
        elif line:
            lines.append(line)
        if len(lines)>25000 or (lines and len(lines[-1])>20000):
            raise ValueError("CALENDAR_LINE_LIMIT")
    return lines

def _events(payload):
    stack=[]
    event=None
    count=0
    lines=_lines(payload)
    if not lines or lines[0]!="BEGIN:VCALENDAR" or lines[-1]!="END:VCALENDAR":
        raise ValueError("CALENDAR_ENVELOPE_INVALID")
    for line in lines:
        head,sep,value=line.partition(":")
        if not sep:
            raise ValueError("CALENDAR_PROPERTY_INVALID")
        if head=="BEGIN":
            if value=="VEVENT":
                if stack!=["VCALENDAR"]:
                    raise ValueError("CALENDAR_STRUCTURE_INVALID")
                event={}
            stack.append(value)
            if len(stack)>5:
                raise ValueError("CALENDAR_NESTING_LIMIT")
        elif head=="END":
            if not stack or stack.pop()!=value:
                raise ValueError("CALENDAR_STRUCTURE_INVALID")
            if value=="VEVENT":
                count+=1
                if count>2000:
                    raise ValueError("CALENDAR_EVENT_LIMIT")
                yield event
                event=None
            if not stack and value!="VCALENDAR":
                raise ValueError("CALENDAR_STRUCTURE_INVALID")
        elif stack==["VCALENDAR","VEVENT"]:
            name=head.split(";",1)[0].upper()
            if name in ("UID","SUMMARY","DTSTART","STATUS","RRULE","RDATE","EXDATE","RECURRENCE-ID"):
                if name in event:
                    raise ValueError("CALENDAR_DUPLICATE_PROPERTY")
                event[name]=(head,value)
    if stack:
        raise ValueError("CALENDAR_STRUCTURE_INVALID")

def _text(value):
    # ICS text escaping; never retain descriptions, alarms or arbitrary URLs.
    value=re.sub(r"\\([nN,;\\])",lambda m:" " if m[1] in ("n","N") else m[1],value)
    value=" ".join(value.split())
    if not 8<=len(value)<=240 or "<" in value or ">" in value:
        raise ValueError("CALENDAR_TITLE_INVALID")
    return value

def _time(head,value):
    if re.fullmatch(r"\d{8}T\d{6}Z",value) and head=="DTSTART":
        return datetime.strptime(value,"%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if head not in ("DTSTART;TZID=America/New_York","DTSTART;TZID=US/Eastern","DTSTART;TZID=US-Eastern",
                    'DTSTART;TZID="America/New_York"','DTSTART;TZID="US/Eastern"'):
        raise ValueError("CALENDAR_TIMEZONE_UNSUPPORTED")
    if not re.fullmatch(r"\d{8}T\d{6}",value):
        raise ValueError("CALENDAR_TIME_INVALID")
    naive=datetime.strptime(value,"%Y%m%dT%H%M%S")
    local=naive.replace(tzinfo=EASTERN)
    # Never invent a time for ambiguous or nonexistent DST wall times.
    if local.utcoffset()!=naive.replace(tzinfo=EASTERN,fold=1).utcoffset():
        raise ValueError("CALENDAR_DST_AMBIGUOUS")
    return local.astimezone(timezone.utc)

def parse(payload,instant):
    output={}
    seen=set()
    supported=0
    for event in _events(payload):
        summary=event.get("SUMMARY",("", ""))[1]
        topic=next((key for key,pattern in TOPICS if re.search(pattern,summary,re.I)),None)
        if topic is None:
            continue
        supported+=1
        uid=event.get("UID",("", ""))[1]
        if not uid or len(uid)>500 or uid in seen:
            raise ValueError("CALENDAR_UID_INVALID")
        seen.add(uid)
        if event.get("STATUS",("", ""))[1].upper()=="CANCELLED":
            continue
        if any(k in event for k in ("RRULE","RDATE","EXDATE","RECURRENCE-ID")):
            raise ValueError("CALENDAR_RECURRENCE_UNSUPPORTED")
        scheduled=_time(*event["DTSTART"]) if "DTSTART" in event else None
        if scheduled is None:
            raise ValueError("CALENDAR_TIME_MISSING")
        if not instant-timedelta(hours=48)<=scheduled<=instant+timedelta(days=30):
            continue
        title=_text(summary)
        ident=sha256(("BLS\n"+uid).encode()).hexdigest()[:40]
        output[ident]={"id":ident,"headline":title,"topic":topic,"scheduled_at":scheduled.isoformat()}
    if not supported:
        raise ValueError("CALENDAR_NO_SUPPORTED_EVENTS")
    if len(output)>100:
        raise ValueError("CALENDAR_WINDOW_LIMIT")
    return sorted(output.values(),key=lambda e:(e["scheduled_at"],e["id"]))

def collect(instant):
    return parse(_download(URL,{}),instant)

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS economic_calendar_snapshot(
        id INTEGER PRIMARY KEY CHECK(id=1),captured_at TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,instant=None,loader=collect):
    if not permitted():
        return
    instant=instant or datetime.now(timezone.utc)
    rows=loader(instant)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO economic_calendar_snapshot VALUES(1,?,?)
           ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
           WHERE excluded.captured_at>=economic_calendar_snapshot.captured_at""",
           (instant.isoformat(),json.dumps(rows,allow_nan=False)))

def read(connect,instant=None):
    if not permitted():
        return empty("DISABLED_OR_NOT_AUTHORIZED")
    instant=instant or datetime.now(timezone.utc)
    with closing(connect()) as db:
        _table(db)
        row=db.execute("SELECT captured_at,payload FROM economic_calendar_snapshot WHERE id=1").fetchone()
    if not row:
        return empty("AWAITING_EVIDENCE")
    stamp=datetime.fromisoformat(row["captured_at"])
    if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
        return empty("STALE_CAPTURE")
    events=[]
    for event in json.loads(row["payload"]):
        scheduled=datetime.fromisoformat(event["scheduled_at"])
        delta=scheduled-instant
        if not -timedelta(hours=48)<=delta<=timedelta(days=30):
            continue
        future=delta>timedelta(0)
        events.append({**event,"status":"SCHEDULED" if future else "SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED",
                       "review_window":future and delta<=timedelta(hours=24)})
    return {**empty("CURRENT_SCHEDULE" if events else "NO_SUPPORTED_EVENTS_IN_WINDOW"),
            "retrieved_at":stamp.isoformat(),"events":events}
