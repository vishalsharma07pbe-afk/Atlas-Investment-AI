"""Source-attributed mutual-fund NAV validation and trailing total-return calculations.

Data is supplied by caller, never fetched or claimed independently verified.
"""
from datetime import date
from math import isfinite
from pydantic import BaseModel,Field,model_validator

class NavPoint(BaseModel):
    as_of:date
    nav:float=Field(gt=0)

class FundNavRequest(BaseModel):
    scheme_code:str=Field(min_length=1,max_length=40,pattern=r"^[A-Za-z0-9_-]+$")
    scheme_name:str=Field(min_length=1,max_length=200)
    source_name:str=Field(min_length=1,max_length=120)
    source_url:str|None=None
    navs:list[NavPoint]=Field(min_length=1,max_length=4000)
    @model_validator(mode="after")
    def validate_navs(self):
        dates=[x.as_of for x in self.navs]
        if dates!=sorted(set(dates)):raise ValueError("NAV dates must be unique and ascending")
        if dates[-1]>date.today():raise ValueError("Future NAV date not allowed")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("Source URL must use HTTPS")
        return self

def analyze_nav(request:FundNavRequest,today:date|None=None)->dict:
    today=today or date.today()
    points=request.navs
    latest=points[-1]
    if latest.as_of>today:raise ValueError("Future NAV date not allowed")
    age=(today-latest.as_of).days
    trailing={}
    for label,days in (("1m",30),("3m",90),("6m",180),("1y",365),("3y",1095),("5y",1825)):
        target=latest.as_of.toordinal()-days
        eligible=[p for p in points[:-1] if p.as_of.toordinal()<=target]
        if not eligible:
            trailing[label]=None
            continue
        start=eligible[-1]
        elapsed=(latest.as_of-start.as_of).days
        if elapsed>days+14:
            trailing[label]=None
            continue
        raw=latest.nav/start.nav
        trailing[label]=round(((raw**(365.25/elapsed)-1) if days>=365 else (raw-1))*100,4)
    return {
        "scheme_code":request.scheme_code,"scheme_name":request.scheme_name,
        "source":{"name":request.source_name,"url":request.source_url,"verification":"USER_SUPPLIED_UNVERIFIED"},
        "latest_nav":{"as_of":latest.as_of.isoformat(),"nav":latest.nav,"age_days":age,
                      "status":"RECENT" if age<=7 else "STALE"},
        "nav_count":len(points),"trailing_returns_pct":trailing,
        "return_method":"CAGR for 1y/3y/5y; simple point-to-point for shorter periods",
        "caveats":["NAV is not an intraday quote","Returns exclude distributions, loads and taxes",
                   "Source provenance is user-supplied and not independently verified",
                   "Trailing returns require a NAV within 14 days of the target date"],
        "ratings":None
    }
