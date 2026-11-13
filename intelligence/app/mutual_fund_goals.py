"""Read-only target-based mutual fund planning using the SIP engine."""
from decimal import Decimal,ROUND_CEILING
from pydantic import BaseModel,Field
from .mutual_fund_planning import SipPlan,FundPlanningRequest,plan_funds,money

class FundGoalRequest(BaseModel):
    target_amount:Decimal=Field(gt=0,le=100000000000,allow_inf_nan=False)
    years:int=Field(ge=1,le=40)
    annual_return_pct:Decimal=Field(ge=-99,le=100,allow_inf_nan=False)
    annual_step_up_pct:Decimal=Field(ge=0,le=100,allow_inf_nan=False,default=Decimal(0))
    initial_amount:Decimal=Field(ge=0,le=1000000000,allow_inf_nan=False,default=Decimal(0))
    current_monthly_sip:Decimal=Field(ge=0,le=100000000,allow_inf_nan=False,default=Decimal(0))

def goal_plan(request:FundGoalRequest)->dict:
    def project(monthly:Decimal)->Decimal:
        plan=SipPlan(monthly_contribution=monthly if monthly>0 else Decimal("0.000001"),
                     annual_return_pct=request.annual_return_pct,years=request.years,
                     annual_step_up_pct=request.annual_step_up_pct,initial_amount=request.initial_amount)
        return Decimal(plan_funds(FundPlanningRequest(sip=plan))["projection"]["projected_value"])
    # Reuse the SIP engine but compute a high-precision baseline before rounding for
    # reliable inverse planning, including negative expected returns.
    baseline=project(Decimal("0.000001"))
    one_unit=project(Decimal(1))
    factor=one_unit-baseline
    if factor<=0:raise ValueError("Unable to derive positive SIP accumulation factor")
    required=max(Decimal(0),(request.target_amount-baseline)/factor)
    # Round up to a whole rupee and confirm against the same projection engine.
    monthly=required.to_integral_value(rounding=ROUND_CEILING)
    if monthly>100000000:raise ValueError("Required monthly SIP exceeds supported limit")
    # Rounded output from the projection engine can differ by a few paise.
    for _ in range(3):
        if project(monthly)>=request.target_amount:break
        monthly+=1
    if monthly>100000000:raise ValueError("Required monthly SIP exceeds supported limit")
    current=project(request.current_monthly_sip)
    shortfall=max(Decimal(0),request.target_amount-current)
    result=plan_funds(FundPlanningRequest(sip=SipPlan(
        monthly_contribution=monthly if monthly>0 else Decimal("0.000001"),
        annual_return_pct=request.annual_return_pct,years=request.years,
        annual_step_up_pct=request.annual_step_up_pct,initial_amount=request.initial_amount)))
    return {"target_amount":money(request.target_amount),
            "required_monthly_sip":money(monthly),
            "additional_monthly_sip":money(max(Decimal(0),monthly-request.current_monthly_sip)),
            "current_monthly_sip":money(request.current_monthly_sip),
            "current_projected_value":money(current),
            "current_shortfall":money(shortfall),
            "required_plan":result["projection"],
            "assumptions":{"annual_return_pct":str(request.annual_return_pct),
                           "annual_step_up_pct":str(request.annual_step_up_pct),
                           "years":request.years,"initial_amount":money(request.initial_amount)},
            "notice":"Illustrative goal planning based on a constant assumed return, not a forecast. No guarantee of achieving the target; excludes inflation, taxes and fees.",
            "stored":False}
