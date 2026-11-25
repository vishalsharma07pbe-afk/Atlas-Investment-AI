"""Fingerprint the shared recent daily evidence, not an assertion of point-in-time history."""
import hashlib
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

VERSION = "REPLAY-EVIDENCE-2"
WINDOW = 250

def exact_isin(value):
    return isinstance(value,str) and re.fullmatch(r"INE[A-Z0-9]{9}",value) is not None

def _canonical(rows,today,window=None):
    try:
        recent=[r for r in rows if date.fromisoformat(r["trade_date"])<today]
        if window is not None:
            recent=recent[-window:]
        if not recent:
            return None
        canonical=[]
        previous=None
        sources=set()
        for row in recent:
            day=date.fromisoformat(row["trade_date"])
            if previous is not None and (day<=previous or (day-previous).days>7):
                return None
            previous=day
            if row["adjustment_status"]!="ADJUSTED" or row["quality_status"]!="PROVIDER_VALIDATED":
                return None
            source=row["source_code"]
            revision=row["revision"]
            if not isinstance(source,str) or not source.strip() or type(revision) is not int or revision<1:
                return None
            sources.add(source)
            values=[Decimal(str(row[k])) for k in ("open","high","low","close","volume")]
            if not all(v.is_finite() for v in values):
                return None
            o,h,l,c,v=values
            if min(o,h,l,c)<=0 or h<max(o,l,c) or l>min(o,c) or v<0 or v!=v.to_integral_value():
                return None
            canonical.append([day.isoformat(),*[format(x.normalize(),"f") for x in values],source,revision])
        if len(sources)!=1:
            return None
        return canonical
    except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError):
        return None

def _digest(value):
    return hashlib.sha256(json.dumps(value,separators=(",",":")).encode()).hexdigest()

def fingerprint(rows,today):
    canonical=_canonical(rows,today,WINDOW)
    return _digest([VERSION,canonical]) if canonical is not None else None

def full_manifest(rows,today):
    """Audit the actual bounded replay input, including older observations."""
    if not isinstance(rows,list) or len(rows)>500:
        return None
    canonical=_canonical(rows,today)
    if canonical is None:
        return None
    return {"version":"FULL-REPLAY-1","first_date":canonical[0][0],"last_date":canonical[-1][0],
            "digest":_digest(["FULL-REPLAY-1",canonical]),
            "observations":{row[0]:_digest(row) for row in canonical}}

def corporate_action_status(instrument,manifest):
    """Do not certify adjustments from an empty or incomplete recorded action ledger."""
    try:
        raw=instrument.get("corporate_action_context")
        if not isinstance(raw,str) or len(raw)>40000:
            return "ACTION_CONTEXT_UNAVAILABLE"
        rows=json.loads(raw)
        if not isinstance(rows,list) or len(rows)>32 or "latest_action_date" not in instrument:
            return "ACTION_CONTEXT_UNAVAILABLE"
        first=date.fromisoformat(manifest["first_date"])
        last=date.fromisoformat(manifest["last_date"])
        dates=[]
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get("action_type"),str) or not row["action_type"].strip():
                return "ACTION_CONTEXT_UNAVAILABLE"
            day=date.fromisoformat(row["ex_date"])
            if day>last:
                return "ACTION_CONTEXT_UNAVAILABLE"
            dates.append(day)
        latest=instrument["latest_action_date"]
        if latest!=(max(dates).isoformat() if dates else None):
            return "ACTION_CONTEXT_UNAVAILABLE"
        if any(first<d<=last for d in dates):
            return "RECORDED_ACTION_RECONCILIATION_REQUIRED"
        return "NO_RECORDED_CROSSING_ACTION"
    except (ValueError,TypeError,KeyError,AttributeError):
        return "ACTION_CONTEXT_UNAVAILABLE"

def revision_audit(manifest,previous):
    current=manifest["observations"]
    prior=previous.get("observations",{}) if isinstance(previous,dict) and previous.get("version")==manifest["version"] else {}
    if not isinstance(prior,dict) or len(prior)>500:
        prior={}
    overlap=current.keys()&prior.keys()
    changed=sorted(d for d in overlap if current[d]!=prior[d])
    # Compare overlapping dates only; a moving bounded history is not evidence
    # of deletion or newly listed securities.
    return {"status":"REVISIONS_DETECTED" if changed else "OVERLAP_UNCHANGED" if overlap else "NO_COMPARABLE_PRIOR_CAPTURE",
            "history_observations":len(current),"first_date":manifest["first_date"],"last_date":manifest["last_date"],
            "overlap_observations":len(overlap),"changed_observations":len(changed),
            "changed_dates":changed[:10],"history_fingerprint":manifest["digest"]}

def session_audit(manifest,calendar,exchange,today):
    """Match the entire observed period through yesterday to stored venue dates."""
    result={"status":"HISTORICAL_CALENDAR_UNAVAILABLE","calendar_days":0,"regular_sessions":0,
            "missing_sessions":0,"unexpected_observations":0,"unknown_days":0,"special_days":0,
            "missing_dates":[],"unexpected_dates":[],"unknown_dates":[],"special_dates":[],
            "notice":"Comparison against locally stored regular sessions and closure policy only; not independent official calendar or point-in-time certification."}
    try:
        first=date.fromisoformat(manifest["first_date"])
        through=today-timedelta(days=1)
        span=(through-first).days+1
        if not 1<=span<=1100 or not isinstance(calendar,dict) or calendar.get("exchange")!=exchange or calendar.get("through")!=through.isoformat():
            return result
        rows=calendar["days"]
        if not isinstance(rows,list) or len(rows)>1100:
            return result
        states={}
        for row in rows:
            day=date.fromisoformat(row["trade_date"])
            state=row["state"]
            if day in states or day>through or day<today-timedelta(days=1100) or state not in ("REGULAR","CLOSED","UNKNOWN","SPECIAL_SESSION_UNSUPPORTED"):
                return result
            states[day]=state
        regular=set()
        unknown=[]
        special=[]
        closed=set()
        for i in range(span):
            day=first+timedelta(days=i)
            key=day.isoformat()
            state=states.get(day,"UNKNOWN")
            if state=="REGULAR":
                regular.add(key)
            elif state=="CLOSED":
                closed.add(key)
            elif state=="SPECIAL_SESSION_UNSUPPORTED":
                special.append(key)
            else:
                unknown.append(key)
        observed=set(manifest["observations"])
        missing=sorted(regular-observed)
        unexpected=sorted(observed&closed)
        result.update(calendar_days=span,regular_sessions=len(regular),missing_sessions=len(missing),
                      unexpected_observations=len(unexpected),unknown_days=len(unknown),special_days=len(special),
                      missing_dates=missing[:10],unexpected_dates=unexpected[:10],unknown_dates=unknown[:10],special_dates=special[:10])
        result["status"]=("HISTORICAL_SESSION_MISMATCH" if missing or unexpected else
                          "HISTORICAL_CALENDAR_INCOMPLETE" if unknown or special else "STORED_SESSIONS_MATCHED")
        return result
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return result
