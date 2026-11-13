"""Broker-neutral reporting contracts. All amounts supplied by the user; no broker API calls."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,Field,model_validator

BROKERS={
 "GROWW":"Groww","ZERODHA":"Zerodha Kite","UPSTOX":"Upstox",
 "ANGEL_ONE":"Angel One","DHAN":"Dhan","FYERS":"FYERS",
 "ICICI_DIRECT":"ICICI Direct","HDFC_SECURITIES":"HDFC Securities",
 "OTHER":"Other / statement import"
}
Asset=Literal["EQUITY","MUTUAL_FUND","ETF"]
class Position(BaseModel):
    broker:str
    account_label:str=Field(min_length=1,max_length=80)
    asset_type:Asset
    instrument_id:str=Field(min_length=1,max_length=80,description="ISIN or scheme identifier, not just symbol")
    display_name:str=Field(min_length=1,max_length=120)
    currency:Literal["INR"]="INR"
    quantity:Decimal=Field(ge=0)
    average_cost:Decimal=Field(ge=0)
    last_price:Decimal|None=Field(default=None,ge=0)
    price_as_of:date|None=None
    source_type:Literal["MANUAL","BROKER_STATEMENT","BROKER_API"]="MANUAL"

    @model_validator(mode="after")
    def valid(self):
        if self.broker not in BROKERS:raise ValueError("Unsupported broker code")
        if self.last_price is not None and self.price_as_of is None:
            raise ValueError("Valuation date required for price")
        return self

class ReportRequest(BaseModel):
    positions:list[Position]=Field(max_length=2000)
    report_date:date
    max_price_age_days:int=Field(default=7,ge=0,le=365)

def report(request:ReportRequest):
    groups=defaultdict(list)
    by_broker=defaultdict(list)
    warnings=[]
    for position in request.positions:
        groups[(position.asset_type,position.instrument_id)].append(position)
        by_broker[(position.broker,position.account_label)].append(position)
    def aggregate(positions):
        cost=sum((p.quantity*p.average_cost for p in positions),Decimal(0))
        valued=[p for p in positions if p.last_price is not None and p.price_as_of is not None
                and 0<=(request.report_date-p.price_as_of).days<=request.max_price_age_days]
        market=sum((p.quantity*p.last_price for p in valued),Decimal(0))
        complete=len(valued)==len(positions)
        return {"invested":str(cost),"recorded_market_value":str(market) if complete else None,
                "unrealized_pnl":str(market-cost) if complete else None,
                "valued_positions":len(valued),"positions":len(positions),
                "valuation_complete":complete}
    instruments=[]
    for (asset,instrument),positions in sorted(groups.items()):
        stats=aggregate(positions)
        if not stats["valuation_complete"]:warnings.append("INCOMPLETE_OR_STALE_PRICE:"+instrument)
        instruments.append({"asset_type":asset,"instrument_id":instrument,
            "display_name":positions[0].display_name,"brokers":sorted({p.broker for p in positions}),
            "total_quantity":str(sum((p.quantity for p in positions),Decimal(0))),**stats})
    brokers=[{"broker":broker,"broker_name":BROKERS[broker],"account_label":account,
        **aggregate(positions)} for (broker,account),positions in sorted(by_broker.items())]
    overall=aggregate(request.positions)
    if not overall["valuation_complete"]:warnings.append("PORTFOLIO_VALUATION_INCOMPLETE")
    return {"status":"USER_SUPPLIED_REPORT","report_date":request.report_date.isoformat(),
        "currency":"INR","broker_accounts":brokers,"consolidated_instruments":instruments,
        "portfolio":overall,"warnings":sorted(set(warnings)),
        "supported_brokers":BROKERS,
        "notice":"Read-only aggregation of supplied positions. No broker connection, source verification, transaction-level cost basis, realized gains, taxes, fees, dividends or trade recommendations."}
