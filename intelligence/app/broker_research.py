"""Attributable broker research comparison; no scraping, fabricated targets or advice."""
from collections import defaultdict
from datetime import date,datetime,timezone
from decimal import Decimal
from statistics import median
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel,Field,model_validator

SOURCES={
 "GROWW":"Groww","ZERODHA":"Zerodha","UPSTOX":"Upstox","ANGEL_ONE":"Angel One",
 "ICICI_DIRECT":"ICICI Direct","HDFC_SECURITIES":"HDFC Securities",
 "MOTILAL_OSWAL":"Motilal Oswal","SHAREKHAN":"Sharekhan",
 "KOTAK_SECURITIES":"Kotak Securities","AXIS_SECURITIES":"Axis Securities",
 "SBI_SECURITIES":"SBI Securities","NUVAMA":"Nuvama",
 "JM_FINANCIAL":"JM Financial","DHAN":"Dhan","FYERS":"FYERS","OTHER":"Other research provider"
}
RATING=Literal["BUY","ACCUMULATE","HOLD","REDUCE","SELL","NOT_RATED"]
class ResearchRecord(BaseModel):
    source:str
    analyst:str|None=Field(default=None,max_length=120)
    instrument_id:str=Field(min_length=3,max_length=80)
    symbol:str=Field(min_length=1,max_length=40)
    published_on:date
    rating:RATING
    target_price:Decimal|None=Field(default=None,gt=0)
    target_currency:Literal["INR"]="INR"
    horizon_months:int|None=Field(default=None,ge=1,le=60)
    report_url:str=Field(min_length=12,max_length=1000)
    report_title:str=Field(min_length=3,max_length=250)
    report_id:str=Field(min_length=1,max_length=120)
    evidence_status:Literal["USER_SUBMITTED","SOURCE_VERIFIED"]="USER_SUBMITTED"

    @model_validator(mode="after")
    def validate_source(self):
        if self.source not in SOURCES:raise ValueError("Unsupported research provider")
        parsed=urlsplit(self.report_url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Report URL must be an HTTPS link without credentials")
        if self.published_on>date.today():raise ValueError("Future publication date")
        return self

class ConsensusRequest(BaseModel):
    instrument_id:str=Field(min_length=3,max_length=80)
    records:list[ResearchRecord]=Field(max_length=300)
    max_age_days:int=Field(default=180,ge=1,le=1095)
    as_of:date=Field(default_factory=date.today)

    @model_validator(mode="after")
    def validate_request(self):
        if self.as_of>date.today():raise ValueError("Future evaluation date")
        if any(r.instrument_id!=self.instrument_id for r in self.records):
            raise ValueError("Mixed instruments not allowed")
        if any(r.published_on>self.as_of for r in self.records):
            raise ValueError("Research cannot postdate evaluation date")
        return self

def consensus(request:ConsensusRequest):
    # One most-recent observation per provider + analyst. Same-day duplicate
    # report IDs are not counted as independent votes.
    seen=set()
    unique=[]
    for r in sorted(request.records,key=lambda x:(-x.published_on.toordinal(),x.source,x.analyst or "",x.report_id)):
        key=(r.source,r.analyst or "")
        if key in seen:continue
        seen.add(key)
        unique.append(r)
    eligible=[r for r in unique if (request.as_of-r.published_on).days<=request.max_age_days]
    ratings=defaultdict(int)
    for r in eligible:ratings[r.rating]+=1
    targets=[r.target_price for r in eligible if r.target_price is not None]
    # Counts are not votes from independent analysts; multiple analysts at one
    # firm can share the same research desk. Show firm count separately.
    firms=len({r.source for r in eligible})
    disagreement=(max(targets)-min(targets)) if len(targets)>1 else None
    return {"status":"RESEARCH_COMPARISON_ONLY","instrument_id":request.instrument_id,
        "as_of":request.as_of.isoformat(),"submitted_records":len(request.records),
        "deduplicated_records":len(unique),"fresh_records":len(eligible),
        "fresh_provider_count":firms,
        "excluded_stale_or_superseded":len(request.records)-len(eligible),
        "rating_counts":{k:ratings[k] for k in ("BUY","ACCUMULATE","HOLD","REDUCE","SELL","NOT_RATED")},
        "targets":{"currency":"INR","count":len(targets),
            "median":str(median(targets)) if targets else None,
            "minimum":str(min(targets)) if targets else None,
            "maximum":str(max(targets)) if targets else None,
            "range":str(disagreement) if disagreement is not None else None},
        "coverage":{"supported_source_codes":list(SOURCES),"submitted_provider_count":len({r.source for r in request.records}),
            "fresh_provider_count":firms,"not_a_marketwide_consensus":True},
        "research":[{"source":r.source,"source_name":SOURCES[r.source],"analyst":r.analyst,
            "rating":r.rating,"target_price":str(r.target_price) if r.target_price is not None else None,
            "horizon_months":r.horizon_months,"published_on":r.published_on.isoformat(),
            "report_title":r.report_title,"report_url":r.report_url,"report_id":r.report_id,
            "evidence_status":r.evidence_status} for r in eligible],
        "blockers":["NO_INDEPENDENT_REPORT_AUTHENTICITY_CHECK",
            "NO_VALIDATED_HISTORICAL_ANALYST_ACCURACY",
            "NO_FUNDAMENTAL_OR_MARKET_CROSS_CHECK",
            "NO_INDEPENDENCE_ADJUSTMENT_FOR_SHARED_RESEARCH"],
        "actionable":False,
        "notice":"User-submitted research comparison, not a verified broker feed or recommendation. Targets are not price forecasts. Coverage depends on supplied reports; no scraping, trading or automated recommendations."}
