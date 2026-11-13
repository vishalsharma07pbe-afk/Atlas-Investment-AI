"""Read-only reconciliation of explicitly mapped fund holdings against user-supplied NAVs."""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field,model_validator

class FundPosition(BaseModel):
    holding_id:int=Field(gt=0)
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    units:Decimal=Field(gt=0)
    invested:Decimal=Field(ge=0)
    recorded_value:Decimal|None=Field(default=None,ge=0)

class FundNav(BaseModel):
    scheme_code:str=Field(min_length=1,max_length=12,pattern=r"^[0-9]+$")
    nav:Decimal=Field(gt=0)
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
    return {"rows":rows,"total_positions":len(request.positions),
            "matched_positions":len(request.positions)-missing,"missing_nav_positions":missing,
            "stale_nav_positions":stale,"total_invested":str(invested_total),
            "matched_estimated_value":str(eligible_value),
            "matched_estimated_pnl":str(eligible_value-eligible_cost),
            "portfolio_estimate_complete":missing==0 and stale==0,
            "portfolio_estimated_value":str(eligible_value) if missing==0 and stale==0 else None,
            "verification":"USER_SUPPLIED_UNVERIFIED",
            "notice":"Research-only estimate. Does not overwrite recorded values or confirm source rights; missing/stale NAVs prevent a complete portfolio estimate."}
