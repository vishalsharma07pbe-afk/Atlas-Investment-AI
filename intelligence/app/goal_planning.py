"""Deterministic goal-based savings projections; never a market-return forecast."""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field,model_validator

class GoalRequest(BaseModel):
    target_amount:Decimal=Field(gt=0,le=1000000000)
    initial_amount:Decimal=Field(default=Decimal(0),ge=0,le=1000000000)
    monthly_contribution:Decimal=Field(default=Decimal(0),ge=0,le=10000000)
    months:int=Field(ge=1,le=600)
    annual_return_percent:Decimal=Field(default=Decimal(0),ge=-30,le=30)

def rounded(value:Decimal)->str:
    return str(value.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def goal_projection(request:GoalRequest)->dict:
    monthly_rate=request.annual_return_percent/Decimal(1200)
    # End-of-month contributions; monthly compounding on the previous balance.
    def project(contribution:Decimal)->tuple[Decimal,list[dict]]:
        balance=request.initial_amount
        checkpoints=[]
        for month in range(1,request.months+1):
            balance=balance*(1+monthly_rate)+contribution
            if month%12==0 or month==request.months:
                checkpoints.append({"month":month,"projected_value":rounded(balance),
                    "total_contributions":rounded(request.initial_amount+contribution*month)})
        return balance,checkpoints
    projected,checkpoints=project(request.monthly_contribution)
    growth_factor=(Decimal(1)+monthly_rate)**request.months
    annuity_factor=sum(((Decimal(1)+monthly_rate)**i for i in range(request.months)),Decimal(0))
    needed=max(Decimal(0),(request.target_amount-request.initial_amount*growth_factor)/annuity_factor)
    # Round required contribution upward so rounded figure doesn't underfund the target.
    required=needed.quantize(Decimal("0.01"),rounding="ROUND_CEILING")
    invested=request.initial_amount+request.monthly_contribution*request.months
    return {"status":"TARGET_MET" if projected>=request.target_amount else "TARGET_SHORTFALL",
        "target_amount":rounded(request.target_amount),"initial_amount":rounded(request.initial_amount),
        "monthly_contribution":rounded(request.monthly_contribution),
        "annual_return_percent":rounded(request.annual_return_percent),
        "months":request.months,"projected_value":rounded(projected),
        "contributed_principal":rounded(invested),"hypothetical_growth":rounded(projected-invested),
        "shortfall":rounded(max(Decimal(0),request.target_amount-projected)),
        "required_monthly_contribution":rounded(required),
        "checkpoints":checkpoints,"method":"END_OF_MONTH_CONTRIBUTIONS_MONTHLY_COMPOUNDING",
        "notice":"Illustrative fixed-rate arithmetic only. Returns are assumptions, not forecasts; excludes taxes, fees, inflation, market volatility and loss of capital."}
