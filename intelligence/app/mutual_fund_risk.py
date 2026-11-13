"""Read-only observable concentration diagnostics for recorded mutual fund holdings.

Does not infer underlying securities, categories, volatility or diversification quality.
"""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field,model_validator

class RiskPosition(BaseModel):
    holding_id:int=Field(gt=0)
    label:str=Field(min_length=1,max_length=120)
    recorded_value:Decimal|None=Field(default=None,ge=0,allow_inf_nan=False)

class FundRiskRequest(BaseModel):
    positions:list[RiskPosition]=Field(min_length=1,max_length=500)
    @model_validator(mode="after")
    def unique_ids(self):
        if len({p.holding_id for p in self.positions})!=len(self.positions):
            raise ValueError("Duplicate holding IDs")
        return self

def pct(value:Decimal)->str:
    return str(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def assess_fund_risk(request:FundRiskRequest)->dict:
    priced=[p for p in request.positions if p.recorded_value is not None]
    unpriced=len(request.positions)-len(priced)
    total=sum((p.recorded_value for p in priced),Decimal(0))
    rows=[]
    if total>0:
        for position in priced:
            weight=position.recorded_value/total
            rows.append({"holding_id":position.holding_id,"label":position.label,
                         "recorded_value":str(position.recorded_value),
                         "weight_pct":pct(weight*100),"weight_fraction":weight})
    rows.sort(key=lambda row:row["weight_fraction"],reverse=True)
    hhi=sum((row["weight_fraction"]**2 for row in rows),Decimal(0))
    top3=sum((row["weight_fraction"] for row in rows[:3]),Decimal(0))
    flags=[]
    if unpriced:flags.append({"code":"INCOMPLETE_VALUATION","severity":"BLOCKER","count":unpriced,
                              "message":"Concentration is calculated for priced holdings only."})
    if total==0:flags.append({"code":"NO_POSITIVE_RECORDED_VALUE","severity":"BLOCKER","count":len(priced),
                              "message":"No positive recorded value is available for weighting."})
    if rows and rows[0]["weight_fraction"]>=Decimal("0.50"):
        flags.append({"code":"SINGLE_HOLDING_AT_LEAST_HALF","severity":"INFO","count":1,
                      "message":"One recorded fund accounts for at least half of priced value; this is not a fund-risk rating."})
    return {"status":"COMPLETE_RECORDED_WEIGHTS" if not unpriced and total>0 else "PARTIAL_OR_UNAVAILABLE",
            "total_positions":len(request.positions),"priced_positions":len(priced),
            "unpriced_positions":unpriced,
            "priced_subset_value":str(total),
            "full_portfolio_value":str(total) if unpriced==0 else None,
            "largest_weight_pct":rows[0]["weight_pct"] if rows else None,
            "top_three_weight_pct":pct(top3*100) if rows else None,
            "hhi":pct(hhi*10000) if rows else None,
            "effective_holdings":pct(Decimal(1)/hhi) if hhi>0 else None,
            "weights":[{"holding_id":r["holding_id"],"label":r["label"],
                        "recorded_value":r["recorded_value"],"weight_pct":r["weight_pct"]} for r in rows],
            "diagnostics":flags,
            "unavailable_metrics":["underlying_security_overlap","sector_exposure","asset_class_exposure",
                                   "volatility","drawdown","beta","tracking_error","expense_ratio"],
            "notice":"Recorded-value concentration only. HHI and effective holdings describe fund-position weights, not true underlying diversification or investment risk. User-supplied prices are unverified.",
            "stored":False}
