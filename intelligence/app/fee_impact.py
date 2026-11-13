"""Deterministic fee drag illustration with explicitly supplied assumptions."""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field

class FeeRequest(BaseModel):
    initial_amount:Decimal=Field(default=Decimal(0),ge=0,le=1000000000)
    monthly_contribution:Decimal=Field(ge=0,le=10000000)
    months:int=Field(ge=1,le=600)
    annual_return_percent:Decimal=Field(default=Decimal(0),ge=-30,le=30)
    annual_expense_ratio_percent:Decimal=Field(default=Decimal(0),ge=0,le=5)
    contribution_fee_percent:Decimal=Field(default=Decimal(0),ge=0,le=5)
    monthly_flat_fee:Decimal=Field(default=Decimal(0),ge=0,le=10000)

def money(n:Decimal)->str:
    return str(n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def fee_impact(req:FeeRequest)->dict:
    gross=req.initial_amount
    net=req.initial_amount
    rate=req.annual_return_percent/Decimal(1200)
    expense=req.annual_expense_ratio_percent/Decimal(1200)
    load=req.contribution_fee_percent/Decimal(100)
    total_expense=Decimal(0)
    total_load=Decimal(0)
    total_flat=Decimal(0)
    checkpoints=[]
    for month in range(1,req.months+1):
        gross=gross*(1+rate)+req.monthly_contribution
        before_fees=net*(1+rate)
        expense_charge=before_fees*expense
        load_charge=req.monthly_contribution*load
        available=before_fees-expense_charge+req.monthly_contribution-load_charge
        flat_charge=min(req.monthly_flat_fee,max(Decimal(0),available))
        net=max(Decimal(0),available-flat_charge)
        total_expense+=expense_charge
        total_load+=load_charge
        total_flat+=flat_charge
        if month%12==0 or month==req.months:
            checkpoints.append({"month":month,"without_fees":money(gross),
                "after_fees":money(net),"fee_drag":money(gross-net)})
    return {"method":"MONTHLY_COMPOUNDING_END_OF_MONTH_CONTRIBUTIONS",
        "without_fees":money(gross),"after_fees":money(net),
        "fee_drag":money(gross-net),
        "expense_ratio_charges":money(total_expense),
        "contribution_charges":money(total_load),
        "flat_charges":money(total_flat),
        "total_charges":money(total_expense+total_load+total_flat),
        "principal":money(req.initial_amount+req.monthly_contribution*req.months),
        "checkpoints":checkpoints,
        "notice":"Illustrative fee drag, not a fund quote, tax calculation, return forecast or recommendation. Gross annual return is a fixed user assumption; expense ratio is applied monthly to post-return balance; contribution fees and flat fees are deducted monthly. Compounding means fee drag differs from summed charges."}
