"""Personal planning scenarios with explicit assumptions and no return prediction."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pydantic import BaseModel, Field, model_validator


class PlanningRequest(BaseModel):
    target_amount: Decimal = Field(gt=0, le=Decimal("1000000000"))
    initial_amount: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("1000000000"))
    monthly_contribution: Decimal = Field(default=Decimal(0), ge=0, le=Decimal("10000000"))
    years: int = Field(ge=1, le=50)
    assumed_return_percent: Decimal = Field(default=Decimal("8"), ge=-20, le=25)
    inflation_percent: Decimal = Field(default=Decimal("5"), ge=0, le=15)
    estimated_tax_drag_percent: Decimal = Field(default=Decimal(0), ge=0, le=10)
    emergency_months: int = Field(default=6, ge=0, le=36)
    income_stability: int = Field(default=3, ge=1, le=5)
    loss_tolerance: int = Field(default=3, ge=1, le=5)
    horizon_tolerance: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def validate_funding(self):
        if self.initial_amount == 0 and self.monthly_contribution == 0:
            raise ValueError("INITIAL_OR_MONTHLY_FUNDING_REQUIRED")
        return self


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _project(request: PlanningRequest, annual_return: Decimal, contribution: Decimal) -> Decimal:
    months = request.years * 12
    net_annual = annual_return - request.estimated_tax_drag_percent
    monthly_rate = net_annual / Decimal(1200)
    balance = request.initial_amount
    for _ in range(months):
        balance = balance * (Decimal(1) + monthly_rate) + contribution
    return balance


def _required_sip(request: PlanningRequest, annual_return: Decimal, target: Decimal) -> Decimal:
    low, high = Decimal(0), Decimal("10000000")
    for _ in range(80):
        middle = (low + high) / 2
        if _project(request, annual_return, middle) >= target:
            high = middle
        else:
            low = middle
    return high.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def personalized_plan(request: PlanningRequest) -> dict:
    score = request.income_stability + request.loss_tolerance + request.horizon_tolerance
    risk_profile = "CONSERVATIVE" if score <= 7 else "BALANCED" if score <= 11 else "GROWTH"
    capacity_flags = []
    if request.emergency_months < 3:
        capacity_flags.append("EMERGENCY_RESERVE_BELOW_THREE_MONTHS")
    if request.years <= 3 and request.loss_tolerance >= 4:
        capacity_flags.append("SHORT_HORIZON_CONFLICTS_WITH_HIGH_LOSS_TOLERANCE")

    future_target = request.target_amount * ((Decimal(1) + request.inflation_percent / 100) ** request.years)
    rates = [
        ("STRESS", max(Decimal("-20"), request.assumed_return_percent - Decimal(4))),
        ("BASE_ASSUMPTION", request.assumed_return_percent),
        ("FAVOURABLE", min(Decimal("25"), request.assumed_return_percent + Decimal(4))),
    ]
    scenarios = []
    for name, rate in rates:
        projected = _project(request, rate, request.monthly_contribution)
        scenarios.append({
            "name": name, "gross_return_assumption_percent": _money(rate),
            "tax_drag_assumption_percent": _money(request.estimated_tax_drag_percent),
            "projected_value": _money(projected),
            "inflation_adjusted_target": _money(future_target),
            "shortfall": _money(max(Decimal(0), future_target - projected)),
            "required_monthly_contribution": _money(_required_sip(request, rate, future_target)),
            "target_met": projected >= future_target,
        })

    base = scenarios[1]
    contribution_gap = max(Decimal(0), Decimal(base["required_monthly_contribution"]) - request.monthly_contribution)
    next_steps = []
    if capacity_flags:
        next_steps.append("Review emergency savings before increasing market-linked contributions.")
    if contribution_gap > 0:
        next_steps.append(f"The base assumption requires about INR {_money(contribution_gap)} more per month.")
    else:
        next_steps.append("The entered monthly contribution reaches the inflation-adjusted target under the base assumption.")
    next_steps.append("Recalculate after material changes to income, goal date, tax treatment, or costs.")

    return {
        "status": "ILLUSTRATIVE_PLAN_ONLY", "risk_profile": risk_profile,
        "risk_score": score, "capacity_flags": capacity_flags,
        "nominal_target_today": _money(request.target_amount),
        "inflation_adjusted_target": _money(future_target),
        "scenarios": scenarios, "next_steps": next_steps,
        "assumptions": {
            "years": request.years,
            "monthly_contribution": _money(request.monthly_contribution),
            "inflation_percent": _money(request.inflation_percent),
            "estimated_tax_drag_percent": _money(request.estimated_tax_drag_percent),
            "compounding": "MONTHLY_END_OF_MONTH_CONTRIBUTIONS",
        },
        "notice": "Goal scenarios are arithmetic based on user assumptions, not forecasts. Tax drag is a simplified user estimate, not tax advice; product rules, fees and realized tax can differ.",
    }
