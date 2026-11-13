"""Read-only mutual-fund SIP projections and portfolio concentration analytics."""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field,model_validator

class SipPlan(BaseModel):
    monthly_contribution:Decimal=Field(gt=0,le=100000000,allow_inf_nan=False)
    annual_return_pct:Decimal=Field(ge=-99,le=100,allow_inf_nan=False)
    years:int=Field(ge=1,le=40)
    annual_step_up_pct:Decimal=Field(ge=0,le=100,allow_inf_nan=False,default=Decimal(0))
    initial_amount:Decimal=Field(ge=0,le=1000000000,allow_inf_nan=False,default=Decimal(0))

class AllocationPosition(BaseModel):
    holding_id:int=Field(gt=0)
    label:str=Field(min_length=1,max_length=120)
    invested:Decimal=Field(ge=0,allow_inf_nan=False)
    recorded_value:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False)

class FundPlanningRequest(BaseModel):
    sip:SipPlan
    positions:list[AllocationPosition]=Field(default_factory=list,max_length=500)
    @model_validator(mode="after")
    def unique_positions(self):
        ids=[p.holding_id for p in self.positions]
        if len(ids)!=len(set(ids)):raise ValueError("Duplicate holding IDs")
        return self

def money(value:Decimal)->str:
    return str(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def plan_funds(request:FundPlanningRequest)->dict:
    plan=request.sip
    monthly_rate=(Decimal(1)+plan.annual_return_pct/Decimal(100))**(Decimal(1)/Decimal(12))-Decimal(1)
    balance=plan.initial_amount
    contributed=plan.initial_amount
    snapshots=[]
    for year in range(1,plan.years+1):
        payment=plan.monthly_contribution*(Decimal(1)+plan.annual_step_up_pct/Decimal(100))**(year-1)
        for _ in range(12):
            balance=(balance+payment)*(Decimal(1)+monthly_rate)
            contributed+=payment
        snapshots.append({"year":year,"contributed":money(contributed),"projected_value":money(balance)})
    known=[p for p in request.positions if p.recorded_value is not None]
    unpriced=len(request.positions)-len(known)
    total=sum((p.recorded_value for p in known),Decimal(0))
    allocations=[{"holding_id":p.holding_id,"label":p.label,"recorded_value":money(p.recorded_value),
                  "weight_pct":money(p.recorded_value/total*100) if total>0 else None}
                 for p in known]
    allocations.sort(key=lambda row:Decimal(row["recorded_value"]),reverse=True)
    return {
        "projection":{"contributed":money(contributed),"projected_value":money(balance),
                      "projected_gain":money(balance-contributed),"annual_snapshots":snapshots,
                      "assumptions":{"annual_return_pct":str(plan.annual_return_pct),
                                     "annual_step_up_pct":str(plan.annual_step_up_pct),
                                     "contribution_timing":"BEGINNING_OF_MONTH",
                                     "compounding":"EFFECTIVE_MONTHLY_FROM_ANNUAL_RATE"}},
        "portfolio":{"total_positions":len(request.positions),"priced_positions":len(known),
                     "unpriced_positions":unpriced,"recorded_total":money(total) if not unpriced else None,
                     "priced_subset_total":money(total),
                     "largest_holding_weight_pct":allocations[0]["weight_pct"] if allocations else None,
                     "allocations":allocations,
                     "complete":unpriced==0},
        "notice":"Illustrative fixed-return SIP projection, not a forecast or recommendation. Excludes fees, taxes and inflation. Portfolio weights use user-recorded values; incomplete portfolios show priced-subset weights only.",
        "source":"USER_SUPPLIED_UNVERIFIED","stored":False
    }
