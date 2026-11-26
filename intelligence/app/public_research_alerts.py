"""Current public research review reminders from existing local snapshots only.

Stable observation identities prevent re-notification on a repeated refresh.
No private holdings, provider requests, forecast, trade or severity calibration.
"""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite
from zoneinfo import ZoneInfo
import re

from . import economic_calendar
from .price_volume_pressure import DOWNSIDE
from .replay_evidence import exact_isin

IST=ZoneInfo("Asia/Kolkata")
FINDINGS={"HIGH_VOLUME_DECLINE_REVIEW":"High-volume decline",
          "HIGH_VOLUME_UPSIDE_REJECTION_REVIEW":"High-volume upside rejection"}

def _stamp(value):
    try:
        result=datetime.fromisoformat(value)
        return result if result.tzinfo is not None else None
    except (TypeError,ValueError):
        return None

def _identity(*parts):
    return "research-"+sha256("|".join(map(str,parts)).encode()).hexdigest()[:40]

def _listing(row,market,day):
    return (row.get("exchange")==market and type(row.get("id")) is int and row["id"]>0
            and isinstance(row.get("symbol"),str) and re.fullmatch(r"[A-Za-z0-9&._ -]{1,40}",row["symbol"])
            and row.get("as_of")==day)

def market_alerts(snapshot,instant):
    if snapshot.get("enabled") is not True:
        return []
    today=instant.astimezone(IST).date()
    alerts={}
    for market in ("NSE","BSE"):
        sections=[s for s in snapshot.get("sections",[]) if s.get("section")==market and s.get("status")=="READY"]
        if len(sections)!=1:
            continue
        section=sections[0]
        stamp=_stamp(section.get("generated_at"))
        if stamp is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
            continue
        result=section.get("result") or {}
        coverage=result.get("discovery_coverage") or {}
        day=coverage.get("expected_session")
        try:
            if (coverage.get("calendar_status")!="PUBLISHED_SESSION" or coverage.get("calendar_checked_on")!=today.isoformat()
                or not 1<=(today-date.fromisoformat(day)).days<=4):
                continue
        except (TypeError,ValueError):
            continue
        if stamp.astimezone(IST).date()<date.fromisoformat(day):
            continue
        for row in (result.get("price_volume_review") or {}).get("downside_items",[])[:5]:
            if not _listing(row,market,day) or not exact_isin(row.get("isin")):
                continue
            pressure=row.get("price_volume_pressure") or {}
            if (pressure.get("status")!="OBSERVED_PRICE_VOLUME_ONLY" or pressure.get("as_of")!=day
                or pressure.get("adjustment_status")!="ADJUSTED" or pressure.get("calendar_status")!="LATEST_SESSION_MATCHED_ONLY"):
                continue
            volume,change=pressure.get("relative_volume"),pressure.get("change_percent")
            if any(type(v) not in (int,float) or not isfinite(v) for v in (volume,change)) or volume<2:
                continue
            findings=sorted(set(pressure.get("findings",[]))&DOWNSIDE)
            if not findings:
                continue
            # A single dated listing reminder covers both existing flags.
            ident=_identity("pressure",market,row["id"],row["isin"],day)
            alerts[ident]={"id":ident,"category":"RISK_WARNING",
                "title":row["symbol"]+" · price/volume review",
                "description":", ".join(FINDINGS[f] for f in findings)+f". {market} daily observation {day}; relative volume {volume:g}x and close change {change:g}%. Bounded sample; adjusted volume basis and cause unverified. Not a trading signal.",
                "event_date":day,"published_at":stamp.isoformat(),"source_name":"ATLAS local price-volume research","source_url":None}
        for row in (result.get("breakout_review") or {}).get("items",[])[:5]:
            if not _listing(row,market,day) or not exact_isin(row.get("isin")):
                continue
            follow=row.get("followthrough") or {}
            if follow.get("status")!="OBSERVED_FOLLOWTHROUGH" or follow.get("as_of")!=day or follow.get("adjustment_status")!="ADJUSTED":
                continue
            for event in follow.get("events",[])[:4]:
                if event.get("status")!="REENTRY_OBSERVED" or event.get("reentry_date")!=day or event.get("direction")!="UPSIDE":
                    continue
                try:
                    if not 1<=(date.fromisoformat(day)-date.fromisoformat(event.get("signal_date"))).days<=21:
                        continue
                except (TypeError,ValueError):
                    continue
                ident=_identity("reentry",market,row["id"],row["isin"],event["signal_date"],day)
                alerts[ident]={"id":ident,"category":"RISK_WARNING","title":row["symbol"]+" · breakout re-entry review",
                    "description":f"{market} adjusted daily observations: upside range break {event['signal_date']}, close back through the frozen boundary {day}. Observed re-entry, not a confirmed trap, forecast or trade instruction.",
                    "event_date":day,"published_at":stamp.isoformat(),"source_name":"ATLAS local breakout research","source_url":None}
    return sorted(alerts.values(),key=lambda row:row["id"])[:50]

def calendar_alerts(calendar,instant):
    if calendar.get("status")!="CURRENT_SCHEDULE" or calendar.get("source_url")!=economic_calendar.SOURCE_PAGE:
        return []
    stamp=_stamp(calendar.get("retrieved_at"))
    if stamp is None or not timedelta(0)<=instant-stamp<=timedelta(hours=24):
        return []
    alerts={}
    for event in calendar.get("events",[])[:100]:
        scheduled=_stamp(event.get("scheduled_at"))
        title=event.get("headline")
        event_id=event.get("id")
        if (event.get("status")!="SCHEDULED" or event.get("review_window") is not True or scheduled is None
            or not timedelta(0)<scheduled-instant<=timedelta(hours=24)
            or not isinstance(title,str) or not 8<=len(title)<=240
            or not isinstance(event_id,str) or not re.fullmatch(r"[a-f0-9]{40}",event_id)):
            continue
        ident=_identity("calendar",event_id,scheduled.astimezone(timezone.utc).isoformat())
        alerts[ident]={"id":ident,"category":"MARKET_EVENT","title":("Upcoming release · "+title)[:160],
            "description":f"Official BLS schedule: {title}; scheduled {scheduled.astimezone(IST).strftime('%Y-%m-%d %H:%M')} IST. Times may change. Review relevant exposure; results and market impact are unverified.",
            "event_date":scheduled.astimezone(IST).date().isoformat(),"published_at":stamp.isoformat(),
            "source_name":"ATLAS reminder · US Bureau of Labor Statistics","source_url":economic_calendar.SOURCE_PAGE}
    return sorted(alerts.values(),key=lambda row:row["id"])[:20]
