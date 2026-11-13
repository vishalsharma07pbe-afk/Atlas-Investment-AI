"""Portfolio concentration checks based solely on manually recorded prices."""
from decimal import Decimal,ROUND_HALF_UP
from pydantic import BaseModel,Field,model_validator

class LimitsRequest(BaseModel):
    max_single_holding_percent:Decimal=Field(default=Decimal(25),ge=1,le=100)
    max_equity_percent:Decimal=Field(default=Decimal(80),ge=0,le=100)
    max_mutual_fund_percent:Decimal=Field(default=Decimal(80),ge=0,le=100)
    max_top_three_percent:Decimal=Field(default=Decimal(60),ge=1,le=100)

def fmt(n:Decimal)->str:
    return str(n.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP))

def concentration_report(holdings,limits:LimitsRequest)->dict:
    priced=[]
    unpriced=[]
    for h in holdings:
        if h.last_price is None:
            unpriced.append({"id":h.id,"symbol":h.symbol,"asset_type":h.asset_type})
            continue
        value=h.quantity*h.last_price
        if value<0:raise ValueError("Negative recorded value")
        priced.append({"id":h.id,"symbol":h.symbol,"asset_type":h.asset_type,"value":value})
    total=sum((x["value"] for x in priced),Decimal(0))
    if total==0:
        return {"status":"NO_PRICED_VALUE","recorded_value":"0.00","holdings":[],
            "unpriced_holdings":unpriced,"exposures":[],"breaches":[],
            "notice":"No positive recorded portfolio value. Concentration cannot be assessed."}
    ranked=sorted(priced,key=lambda x:(-x["value"],x["symbol"],x["id"]))
    holdings_out=[]
    breaches=[]
    for item in ranked:
        weight=item["value"]*100/total
        holdings_out.append({"id":item["id"],"symbol":item["symbol"],"asset_type":item["asset_type"],
            "recorded_value":fmt(item["value"]),"weight_percent":fmt(weight)})
        if weight>limits.max_single_holding_percent:
            breaches.append({"type":"SINGLE_HOLDING","label":item["symbol"],
                "actual_percent":fmt(weight),"limit_percent":fmt(limits.max_single_holding_percent)})
    exposures=[]
    for asset_type,limit in (("EQUITY",limits.max_equity_percent),("MUTUAL_FUND",limits.max_mutual_fund_percent)):
        amount=sum((x["value"] for x in ranked if x["asset_type"]==asset_type),Decimal(0))
        weight=amount*100/total
        exposures.append({"asset_type":asset_type,"recorded_value":fmt(amount),"weight_percent":fmt(weight),
            "limit_percent":fmt(limit)})
        if weight>limit:
            breaches.append({"type":"ASSET_TYPE","label":asset_type,
                "actual_percent":fmt(weight),"limit_percent":fmt(limit)})
    top_three=sum((x["value"] for x in ranked[:3]),Decimal(0))*100/total
    if top_three>limits.max_top_three_percent:
        breaches.append({"type":"TOP_THREE","label":"Top 3 recorded holdings",
            "actual_percent":fmt(top_three),"limit_percent":fmt(limits.max_top_three_percent)})
    return {"status":"PARTIAL_PRICE_COVERAGE" if unpriced else "COMPLETE_PRICED_SUBSET",
        "recorded_value":fmt(total),"price_source":"MANUALLY_RECORDED_NOT_LIVE",
        "holdings":holdings_out,"exposures":exposures,
        "top_three_percent":fmt(top_three),"unpriced_holdings":unpriced,
        "breaches":breaches,"breach_count":len(breaches),
        "notice":"Checks user-defined thresholds on the priced subset only; missing prices are excluded. No look-through into mutual fund holdings, correlation, diversification guarantees, live quotes, trading advice or orders."}
