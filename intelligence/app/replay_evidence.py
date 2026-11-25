"""Fingerprint the shared recent daily evidence, not an assertion of point-in-time history."""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

VERSION = "REPLAY-EVIDENCE-2"
WINDOW = 250

def exact_isin(value):
    return isinstance(value,str) and re.fullmatch(r"INE[A-Z0-9]{9}",value) is not None

def fingerprint(rows,today):
    try:
        recent=[r for r in rows if date.fromisoformat(r["trade_date"])<today][-WINDOW:]
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
        return hashlib.sha256(json.dumps([VERSION,canonical],separators=(",",":")).encode()).hexdigest()
    except (KeyError,TypeError,ValueError,InvalidOperation,OverflowError):
        return None
