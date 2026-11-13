"""Research-only institutional flow evidence: user-supplied, no feed claims."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class FlowRecord(BaseModel):
    trade_date: date
    market: Literal["NSE", "BSE", "INDIA_COMBINED"]
    participant: Literal["FII", "FPI", "DII", "RETAIL"]
    buy_crore_inr: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    sell_crore_inr: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    source_name: str = Field(min_length=3, max_length=160)
    source_url: str | None = Field(default=None, max_length=500)
    verification: Literal["USER_REPORTED", "SOURCE_CHECKED"] = "USER_REPORTED"

    @model_validator(mode="after")
    def validate_date(self):
        if self.trade_date > date.today():
            raise ValueError("Future flow date is not allowed")
        return self

class FlowRequest(BaseModel):
    records: list[FlowRecord] = Field(min_length=1, max_length=120)

def analyze_flows(records: list[FlowRecord]):
    keys=set()
    rows=[]
    for r in records:
        key=(r.trade_date,r.market,r.participant)
        if key in keys:
            raise ValueError("Duplicate market, date and participant; avoid double counting")
        keys.add(key)
        net=r.buy_crore_inr-r.sell_crore_inr
        rows.append({
            "trade_date":r.trade_date.isoformat(),"market":r.market,
            "participant":r.participant,"buy_crore_inr":str(r.buy_crore_inr),
            "sell_crore_inr":str(r.sell_crore_inr),"net_crore_inr":str(net),
            "direction":"NET_BUY" if net>0 else "NET_SELL" if net<0 else "BALANCED",
            "source_name":r.source_name,"source_url":r.source_url,
            "verification":r.verification,
        })
    rows.sort(key=lambda r:(r["trade_date"],r["market"],r["participant"]),reverse=True)
    return {
        "status":"USER_SUPPLIED_EVIDENCE_ONLY",
        "record_count":len(rows),"records":rows,
        "independent_verification":False,
        "notice":"Arithmetic on supplied participant flow records only. Not a live exchange feed. No FII/DII signal, prediction or recommendation. Do not aggregate overlapping market scopes.",
    }
