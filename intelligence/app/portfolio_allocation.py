"""Read-only portfolio allocation and hypothetical contribution planner.

No prices are fetched, no transactions are proposed or executed. Unpriced holdings
are excluded explicitly; cash-only contributions cannot reduce existing positions.
"""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field,model_validator

def money(n:Decimal)->str:
    return str(n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

class Target(BaseModel):
    asset_type:str=Field(min_length=1,max_length=40,pattern=r"^[A-Z0-9_]+$")
    weight_percent:Decimal=Field(ge=0,le=100)

class PlanRequest(BaseModel):
    targets:list[Target]=Field(min_length=1,max_length=20)
    contribution:Decimal=Field(default=Decimal("0"),ge=0,le=100000000)
    @model_validator(mode="after")
    def validate_targets(self):
        if len({t.asset_type for t in self.targets})!=len(self.targets):
            raise ValueError("Duplicate asset type target")
        if sum((t.weight_percent for t in self.targets),Decimal(0))!=100:
            raise ValueError("Target weights must total 100%")
        return self

def allocation_plan(holdings,request:PlanRequest)->dict:
    values={}
    unpriced=[]
    for h in holdings:
        if h.last_price is None:
            unpriced.append({"id":h.id,"symbol":h.symbol,"asset_type":h.asset_type})
            continue
        value=h.quantity*h.last_price
        if value<0:raise ValueError("Negative recorded value")
        values[h.asset_type]=values.get(h.asset_type,Decimal(0))+value
    total=sum(values.values(),Decimal(0))
    target_map={t.asset_type:t.weight_percent for t in request.targets}
    if total==0:
        return {"status":"NO_PRICED_VALUE","price_source":"MANUALLY_RECORDED_NOT_LIVE",
            "unpriced_holdings":unpriced,"recorded_value":"0.00",
            "contribution":money(request.contribution),"allocations":[],
            "unallocated_contribution":money(request.contribution),
            "notice":"No recorded positive portfolio value; target contribution allocation is not calculated."}
    categories=sorted(set(values)|set(target_map))
    post_total=total+request.contribution
    deficits={key:max(Decimal(0),post_total*target_map.get(key,Decimal(0))/100-values.get(key,Decimal(0))) for key in categories}
    deficit_total=sum(deficits.values(),Decimal(0))
    # Contribution-only allocation is proportional to positive target deficits.
    spend=min(request.contribution,deficit_total)
    planned={key:(spend*deficits[key]/deficit_total if deficit_total else Decimal(0)) for key in categories}
    allocations=[]
    for key in categories:
        current=values.get(key,Decimal(0))
        desired=post_total*target_map.get(key,Decimal(0))/100
        allocations.append({"asset_type":key,"recorded_value":money(current),
            "current_weight_percent":money(current*100/total),
            "target_weight_percent":money(target_map.get(key,Decimal(0))),
            "target_value_after_contribution":money(desired),
            "hypothetical_contribution":money(planned[key]),
            "remaining_target_gap":money(desired-current-planned[key])})
    return {"status":"PARTIAL_PRICE_COVERAGE" if unpriced else "COMPLETE_PRICED_SUBSET",
        "price_source":"MANUALLY_RECORDED_NOT_LIVE",
        "recorded_value":money(total),"contribution":money(request.contribution),
        "unpriced_holdings":unpriced,"allocations":allocations,
        "unallocated_contribution":money(request.contribution-spend),
        "notice":"Hypothetical contribution-only allocation using recorded prices. Rounding may create paise differences. No sales, fees, taxes, live quotes, investment advice or trade execution."}
