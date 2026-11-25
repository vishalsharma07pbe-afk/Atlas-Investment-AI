"""Conservative reconciliation of BLS schedules with current official RSS evidence."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import re

EASTERN=ZoneInfo("America/New_York")
# Exact schedule series labels, with optional explicit month/year suffix.
SERIES={"consumer price index":("BLS_CPI","cpi"),
        "producer price index":("BLS_PPI","ppi"),
        "employment situation":("BLS_JOBS","empsit")}
MONTH=r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
NOTICE="Review the actual release; numerical results, consensus surprise and market impact remain unverified."
UNMATCHED="No unique compatible official archive headline. This does not prove that the release was delayed or absent."

def _series(title):
    if not isinstance(title,str):
        return None
    normalized=" ".join(title.casefold().split())
    for name,series in SERIES.items():
        if re.fullmatch(re.escape(name)+r"(?:\s*[-–—:]\s*"+MONTH+r"(?:\s+20\d{2})?)?",normalized):
            return series
    return None

def _stamp(value):
    result=datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return result

def _eligible(event,series,scheduled,instant):
    try:
        feed,code=series
        if (event.get("status")!="PUBLISHED_FEED_HEADLINE" or event.get("source_name")!="US Bureau of Labor Statistics"
            or event.get("geography")!="US" or feed not in event.get("feed_ids",[])
            or not isinstance(event.get("id"),str) or not isinstance(event.get("headline"),str)):
            return False
        p=urlsplit(event["source_url"])
        expected="/news.release/archives/"+code+"_"+scheduled.astimezone(EASTERN).strftime("%m%d%Y")+".htm"
        if (p.scheme!="https" or p.netloc not in ("www.bls.gov","bls.gov") or p.path!=expected or p.query or p.fragment):
            return False
        published=_stamp(event["published_at"])
        return (scheduled<=published<=instant and published-scheduled<=timedelta(hours=12)
                and published.astimezone(EASTERN).date()==scheduled.astimezone(EASTERN).date())
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return False

def attach(snapshot,instant):
    """Add a separate evidence match; never change original schedule status."""
    if not snapshot.get("enabled"):
        return snapshot
    calendar=snapshot.get("economic_calendar") or {}
    releases=snapshot.get("global_releases") or {}
    if calendar.get("status")!="CURRENT_SCHEDULE":
        return snapshot
    events=calendar.get("events",[])
    headlines=releases.get("events",[])
    # Only current source snapshots can contribute to a match.
    feeds={s.get("source") for s in releases.get("sources",[]) if s.get("status")=="CURRENT_FEED"}
    matches={}
    claims={}
    for index,row in enumerate(events):
        if row.get("status")!="SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED":
            continue
        series=_series(row.get("headline"))
        result={"status":"SERIES_NOT_SUPPORTED","notice":UNMATCHED}
        row["release_match"]=result
        if not series:
            continue
        if series[0] not in feeds:
            result["status"]="CURRENT_RELEASE_FEED_UNAVAILABLE"
            continue
        try:
            scheduled=_stamp(row["scheduled_at"])
        except (ValueError,TypeError,KeyError,AttributeError):
            result["status"]="INVALID_SCHEDULE_TIME"
            continue
        if not timedelta(0)<=instant-scheduled<=timedelta(hours=48):
            result["status"]="INVALID_SCHEDULE_TIME"
            continue
        found=[e for e in headlines if _eligible(e,series,scheduled,instant)]
        matches[index]=found
        for e in found:
            claims[e["id"]]=claims.get(e["id"],0)+1
    for index,found in matches.items():
        result=events[index]["release_match"]
        if not found:
            result["status"]="NO_COMPATIBLE_HEADLINE"
        elif len(found)!=1 or claims[found[0]["id"]]!=1:
            result["status"]="AMBIGUOUS_RELEASE_MATCH"
        else:
            e=found[0]
            result.update(status="MATCHED_OFFICIAL_RELEASE_HEADLINE",headline=e["headline"],
                          source_url=e["source_url"],published_at=e["published_at"],
                          notice=NOTICE)
    return snapshot
