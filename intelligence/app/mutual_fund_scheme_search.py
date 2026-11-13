"""Bounded scheme search over a user-supplied AMFI-style NAV snapshot.

No remote retrieval, entitlement claim, persistence or fuzzy scheme identity matching.
"""
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from pydantic import BaseModel,Field,model_validator

class SchemeSearchRequest(BaseModel):
    text:str=Field(min_length=1,max_length=2_000_000)
    query:str=Field(min_length=2,max_length=120)
    limit:int=Field(default=20,ge=1,le=50)

    @model_validator(mode="after")
    def check_query(self):
        if not self.query.strip():raise ValueError("Search query cannot be blank")
        return self

def search_schemes(request:SchemeSearchRequest,today:date|None=None)->dict:
    today=today or date.today()
    if len(request.text.encode("utf-8"))>2_000_000:raise ValueError("NAV snapshot exceeds size limit")
    needle=request.query.strip().casefold()
    matches=[]
    seen=set()
    duplicates=set()
    scanned=0
    for line in request.text.splitlines():
        fields=line.split(";")
        if len(fields)<6:continue
        code=fields[0].strip()
        if not code.isascii() or not code.isdecimal() or len(code)>12:continue
        scanned+=1
        if scanned>50_000:raise ValueError("Too many NAV rows")
        name=fields[3].strip()
        if not name or len(name)>240:continue
        if needle not in name.casefold() and needle not in code:continue
        if code in seen:
            duplicates.add(code)
            continue
        seen.add(code)
        try:
            nav=Decimal(fields[4].strip())
            stamp=datetime.strptime(fields[5].strip(),"%d-%b-%Y").date()
            if not nav.is_finite() or nav<=0 or stamp>today:continue
            value=float(nav)
            if value==float("inf") or value<=0:continue
        except (InvalidOperation,ValueError,OverflowError):
            continue
        matches.append({"scheme_code":code,"scheme_name":name,"nav":value,
                        "as_of":stamp.isoformat(),"status":"RECENT" if (today-stamp).days<=7 else "STALE"})
    matches=[item for item in matches if item["scheme_code"] not in duplicates]
    matches.sort(key=lambda item:(item["scheme_name"].casefold(),item["scheme_code"]))
    return {"schemes":matches[:request.limit],"matches_total":len(matches),
            "truncated":len(matches)>request.limit,"rows_scanned":scanned,
            "duplicate_scheme_codes":sorted(duplicates),
            "source":{"name":"AMFI-style NAV text supplied by user","verification":"USER_SUPPLIED_UNVERIFIED"},
            "notice":"Search results are from user-supplied snapshot text only. Scheme identity and data rights are not independently verified; never auto-map holdings."}
