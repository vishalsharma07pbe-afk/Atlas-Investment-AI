"""Read-only, fail-closed preflight for a caller-supplied mutual fund NAV refresh."""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field,model_validator

class NavRefreshRecord(BaseModel):
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    nav:Decimal=Field(gt=0,allow_inf_nan=False)
    as_of:date

class NavRefreshPreflightRequest(BaseModel):
    source_name:str=Field(min_length=1,max_length=120)
    source_authorized:bool=False
    expected_scheme_codes:list[str]=Field(min_length=1,max_length=500)
    records:list[NavRefreshRecord]=Field(min_length=1,max_length=500)
    @model_validator(mode="after")
    def validate_expected(self):
        if any(not x.isascii() or not x.isdigit() or len(x)>12 or len(x)==0 for x in self.expected_scheme_codes):
            raise ValueError("Expected scheme codes must be numeric")
        if len(set(self.expected_scheme_codes))!=len(self.expected_scheme_codes):
            raise ValueError("Duplicate expected scheme code")
        return self

def preflight_nav_refresh(request:NavRefreshPreflightRequest,today:date|None=None)->dict:
    today=today or date.today()
    expected=set(request.expected_scheme_codes)
    found={}
    duplicates=set()
    future=set()
    stale=set()
    for record in request.records:
        code=record.scheme_code
        if code in found:duplicates.add(code)
        found[code]=record
        age=(today-record.as_of).days
        if age<0:future.add(code)
        elif age>7:stale.add(code)
    missing=sorted(expected-set(found))
    unexpected=sorted(set(found)-expected)
    matched_dates=sorted({found[code].as_of.isoformat() for code in expected&set(found)})
    blockers=[]
    if not request.source_authorized:blockers.append("SOURCE_AUTHORIZATION_NOT_CONFIRMED")
    if duplicates:blockers.append("DUPLICATE_SCHEME_CODES")
    if missing:blockers.append("MISSING_EXPECTED_SCHEMES")
    if unexpected:blockers.append("UNEXPECTED_SCHEME_CODES")
    if future:blockers.append("FUTURE_NAV_DATES")
    if stale:blockers.append("STALE_NAV_DATES")
    if len(matched_dates)>1:blockers.append("MIXED_VALUATION_DATES")
    return {"status":"READY_FOR_MANUAL_REVIEW" if not blockers else "BLOCKED",
            "blockers":blockers,
            "details":{"missing_scheme_codes":missing,"unexpected_scheme_codes":unexpected,
                       "duplicate_scheme_codes":sorted(duplicates),"future_scheme_codes":sorted(future),
                       "stale_scheme_codes":sorted(stale),"matched_as_of_dates":matched_dates,
                       "expected_count":len(expected),"received_count":len(request.records)},
            "source":{"name":request.source_name,"authorization_user_attested":request.source_authorized,
                      "verification":"USER_ATTESTED_NOT_INDEPENDENTLY_VERIFIED"},
            "stored":False,"refresh_executed":False,
            "notice":"Preflight only: no NAV retrieval, persistence or portfolio updates. READY_FOR_MANUAL_REVIEW is not provider authorization or verification."}
