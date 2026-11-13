"""Read-only reconciliation of explicitly mapped fund holdings against user-supplied NAVs."""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field,model_validator

class FundPosition(BaseModel):
    holding_id:int=Field(gt=0)
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    units:Decimal=Field(gt=0,allow_inf_nan=False)
    invested:Decimal=Field(ge=0,allow_inf_nan=False)
    recorded_value:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False)

class FundNav(BaseModel):
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    nav:Decimal=Field(gt=0,allow_inf_nan=False)
    as_of:date
    source_name:str=Field(min_length=1,max_length=120)

class FundReconciliationRequest(BaseModel):
    positions:list[FundPosition]=Field(min_length=1,max_length=500)
    navs:list[FundNav]=Field(min_length=1,max_length=500)
    @model_validator(mode="after")
    def unique_identifiers(self):
        if len({x.holding_id for x in self.positions})!=len(self.positions):
            raise ValueError("Duplicate holding IDs")
        if len({x.scheme_code for x in self.navs})!=len(self.navs):
            raise ValueError("Duplicate NAV scheme codes")
        if any(x.as_of>date.today() for x in self.navs):
            raise ValueError("Future NAV date")
        return self

def reconcile_funds(request:FundReconciliationRequest,today:date|None=None)->dict:
    today=today or date.today()
    navs={x.scheme_code:x for x in request.navs}
    rows=[]
    invested_total=Decimal(0)
    eligible_value=Decimal(0)
    eligible_cost=Decimal(0)
    missing=0
    stale=0
    for position in request.positions:
        invested_total+=position.invested
        nav=navs.get(position.scheme_code)
        if nav is None:
            missing+=1
            rows.append({"holding_id":position.holding_id,"scheme_code":position.scheme_code,
                         "status":"MISSING_NAV","estimated_value":None,"difference_from_recorded":None})
            continue
        age=(today-nav.as_of).days
        if age<0:raise ValueError("Future NAV date")
        if age>7:stale+=1
        value=position.units*nav.nav
        eligible_value+=value
        eligible_cost+=position.invested
        rows.append({"holding_id":position.holding_id,"scheme_code":position.scheme_code,
                     "status":"STALE_NAV" if age>7 else "MATCHED_UNVERIFIED",
                     "source_name":nav.source_name,"nav_as_of":nav.as_of.isoformat(),"nav_age_days":age,
                     "units":str(position.units),"nav":str(nav.nav),
                     "estimated_value":str(value),
                     "recorded_value":str(position.recorded_value) if position.recorded_value is not None else None,
                     "difference_from_recorded":str(value-position.recorded_value) if position.recorded_value is not None else None})
    used_codes={position.scheme_code for position in request.positions}
    unused_codes=sorted(set(navs)-used_codes)
    no_recorded=sum(position.recorded_value is None for position in request.positions)
    source_names=sorted({navs[code].source_name for code in used_codes if code in navs})
    matched_dates={navs[code].as_of for code in used_codes if code in navs}
    diagnostics=[]
    if missing:
        diagnostics.append({"code":"MISSING_NAV","severity":"BLOCKER","count":missing,
                            "message":"Holdings lack matching scheme-code NAVs."})
    if stale:
        diagnostics.append({"code":"STALE_NAV","severity":"BLOCKER","count":stale,
                            "message":"NAVs older than seven days cannot support a complete estimate."})
    if len(matched_dates)>1:
        diagnostics.append({"code":"MIXED_AS_OF_DATES","severity":"BLOCKER","count":len(matched_dates),
                            "message":"Matched NAVs have different valuation dates."})
    if len(source_names)>1:
        diagnostics.append({"code":"MULTIPLE_SOURCES","severity":"INFO","count":len(source_names),
                            "message":"Matched NAVs were supplied from different named sources."})
    if unused_codes:
        diagnostics.append({"code":"UNUSED_NAV_CODES","severity":"INFO","count":len(unused_codes),
                            "message":"Some supplied scheme codes are not mapped to any holding."})
    if no_recorded:
        diagnostics.append({"code":"NO_RECORDED_VALUE","severity":"INFO","count":no_recorded,
                            "message":"Some holdings have no recorded value for difference calculation."})
    diagnostics.append({"code":"UNVERIFIED_PROVENANCE","severity":"WARNING","count":len(source_names),
                        "message":"All NAV source names are user-supplied, not independently verified."})
    return {"rows":rows,"total_positions":len(request.positions),
            "diagnostics":diagnostics,
            "quality_summary":{"missing_nav":missing,"stale_nav":stale,
                               "unused_nav_scheme_codes":unused_codes,
                               "matched_nav_as_of_dates":sorted(day.isoformat() for day in matched_dates),
                               "matched_source_names":source_names,
                               "holdings_without_recorded_value":no_recorded},
            "matched_positions":len(request.positions)-missing,"missing_nav_positions":missing,
            "stale_nav_positions":stale,"total_invested":str(invested_total),
            "matched_estimated_value":str(eligible_value),
            "matched_estimated_pnl":str(eligible_value-eligible_cost),
            "portfolio_estimate_complete":missing==0 and stale==0 and len(matched_dates)==1,
            "portfolio_estimated_value":str(eligible_value) if missing==0 and stale==0 and len(matched_dates)==1 else None,
            "verification":"USER_SUPPLIED_UNVERIFIED",
            "notice":"Research-only estimate. Does not overwrite recorded values or confirm source rights; missing, stale or mixed-date NAVs prevent a complete synchronized portfolio estimate."}
