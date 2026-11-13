"""Bounded, opt-in AMFI NAV text parsing and read-only latest-NAV lookup.

AMFI NAVAll.txt is a published scheme snapshot, not historical total-return data.
No persistence, scheduled network fetch or independently verified feed entitlement.
"""
from datetime import datetime,date
from decimal import Decimal,InvalidOperation
from math import isfinite
from pydantic import BaseModel,Field

MAX_TEXT_BYTES=2_000_000
MAX_ROWS=50_000

class AmfiImportRequest(BaseModel):
    text:str=Field(min_length=1,max_length=MAX_TEXT_BYTES)
    scheme_codes:list[str]=Field(min_length=1,max_length=200)
    source_name:str="AMFI NAV text supplied by user"

def parse_amfi(text:str,scheme_codes:list[str],today:date|None=None)->dict:
    today=today or date.today()
    if len(text.encode("utf-8"))>MAX_TEXT_BYTES:raise ValueError("NAV file exceeds size limit")
    if len(scheme_codes)>200 or not scheme_codes or any(not code.isascii() or not code.isdecimal() or len(code)>12 for code in scheme_codes):
        raise ValueError("Invalid scheme code selection")
    if len(set(scheme_codes))!=len(scheme_codes):raise ValueError("Duplicate scheme codes")
    selected=set(scheme_codes)
    found={}
    seen=set()
    duplicates=set()
    rejected=0
    rows=0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("Scheme Code","Open Ended","Close Ended","Interval Fund")):
            continue
        parts=line.split(";")
        code=parts[0].strip()
        if not code.isascii() or not code.isdecimal():continue
        rows+=1
        if rows>MAX_ROWS:raise ValueError("Too many scheme rows")
        if code not in selected:continue
        if code in seen:
            rejected+=1
            duplicates.add(code)
            found.pop(code,None)
            continue
        seen.add(code)
        if len(parts)<6:
            rejected+=1
            continue
        try:
            value=Decimal(parts[4].strip())
            if not value.is_finite() or value<=0:raise ValueError("Invalid NAV")
            nav_date=datetime.strptime(parts[5].strip(),"%d-%b-%Y").date()
            if nav_date>today:raise ValueError("Future NAV")
            name=parts[3].strip()
            if not name or len(name)>240:raise ValueError("Invalid scheme name")
            nav=float(value)
            if not isfinite(nav) or nav<=0:raise ValueError("NAV exceeds supported numeric range")
            found[code]={"scheme_code":code,"scheme_name":name,"nav":nav,
                         "as_of":nav_date.isoformat(),"age_days":(today-nav_date).days,
                         "status":"RECENT" if (today-nav_date).days<=7 else "STALE"}
        except (ValueError,InvalidOperation,OverflowError):
            rejected+=1
    # Never silently return a duplicate scheme as valid.
    missing=[code for code in scheme_codes if code not in found]
    return {"source":{"name":"AMFI NAV text supplied by user","verification":"USER_SUPPLIED_UNVERIFIED"},
            "rows_scanned":rows,"rejected_rows":rejected,
            "duplicate_scheme_codes":sorted(duplicates),
            "schemes":[found[code] for code in scheme_codes if code in found],
            "missing_scheme_codes":missing,"historical_returns_available":False,
            "notice":"Daily NAV snapshot only; source, scheme mapping and data rights not independently verified."}
