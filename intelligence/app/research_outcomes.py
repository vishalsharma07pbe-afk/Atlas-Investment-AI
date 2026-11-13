"""Historical broker-research outcome review; no lookahead or fabricated price series."""
from datetime import date,timedelta
from decimal import Decimal
from statistics import median
from pydantic import BaseModel,Field,model_validator
from .broker_research import ResearchRecord,SOURCES

class PricePoint(BaseModel):
    trade_date:date
    close:Decimal=Field(gt=0)
    adjustment_status:str="UNVERIFIED"
    source_revision:str=Field(min_length=1,max_length=120)

class OutcomeRequest(BaseModel):
    instrument_id:str=Field(min_length=3,max_length=80)
    reports:list[ResearchRecord]=Field(max_length=200)
    prices:list[PricePoint]=Field(max_length=3000)
    as_of:date=Field(default_factory=date.today)
    horizon_days:int=Field(default=90,ge=5,le=730)
    max_entry_delay_days:int=Field(default=5,ge=0,le=10)
    max_exit_delay_days:int=Field(default=5,ge=0,le=10)

    @model_validator(mode="after")
    def validate(self):
        if self.as_of>date.today():raise ValueError("Future evaluation date")
        if any(r.instrument_id!=self.instrument_id or r.published_on>self.as_of for r in self.reports):
            raise ValueError("Reports must match instrument and predate evaluation")
        if any(p.trade_date>self.as_of for p in self.prices):
            raise ValueError("Future price data is not permitted")
        if len({p.trade_date for p in self.prices})!=len(self.prices):
            raise ValueError("Duplicate price dates")
        return self

def evaluate(request:OutcomeRequest):
    """Only use a strictly later close as entry, then a close at/after horizon end."""
    prices=sorted(request.prices,key=lambda p:p.trade_date)
    eligible_prices=[p for p in prices if p.adjustment_status in ("ADJUSTED","RAW_UNADJUSTED")]
    outcomes=[]
    for r in request.reports:
        maturity=r.published_on+timedelta(days=request.horizon_days)
        blockers=[]
        if maturity>request.as_of:blockers.append("HORIZON_NOT_MATURE")
        entry=next((p for p in eligible_prices if r.published_on<p.trade_date<=r.published_on+timedelta(days=request.max_entry_delay_days)),None)
        exit_point=next((p for p in eligible_prices if maturity<=p.trade_date<=maturity+timedelta(days=request.max_exit_delay_days)),None) if maturity<=request.as_of else None
        if entry is None:blockers.append("NO_POST_PUBLICATION_ENTRY_PRICE")
        if exit_point is None and maturity<=request.as_of:blockers.append("NO_MATURE_EXIT_PRICE")
        if entry and exit_point and entry.adjustment_status!=exit_point.adjustment_status:
            blockers.append("MIXED_PRICE_ADJUSTMENTS")
        if entry and exit_point and entry.source_revision!=exit_point.source_revision:
            blockers.append("MIXED_SOURCE_REVISIONS")
        # Even if price labels agree, declarations are not independent corporate-action verification.
        blockers.append("PRICE_PROVENANCE_AND_ADJUSTMENTS_UNVERIFIED")
        observed_return=None
        if entry and exit_point and not any(x in blockers for x in ("HORIZON_NOT_MATURE","MIXED_PRICE_ADJUSTMENTS","MIXED_SOURCE_REVISIONS")):
            observed_return=str((exit_point.close/entry.close-Decimal(1))*Decimal(100))
        outcomes.append({"source":r.source,"source_name":SOURCES[r.source],
            "report_id":r.report_id,"rating":r.rating,"published_on":r.published_on.isoformat(),
            "horizon_end":maturity.isoformat(),"entry_date":entry.trade_date.isoformat() if entry else None,
            "exit_date":exit_point.trade_date.isoformat() if exit_point else None,
            "observed_price_return_pct_unverified":observed_return,
            "blockers":sorted(set(blockers)),"accuracy_verified":False})
    return {"status":"HISTORICAL_OUTCOME_REVIEW_ONLY","instrument_id":request.instrument_id,
        "as_of":request.as_of.isoformat(),"horizon_days":request.horizon_days,
        "reports_reviewed":len(outcomes),"outcomes":outcomes,
        "verified_analyst_accuracy_score":None,
        "notice":"Unverified, user-supplied prices and reports. Observed returns exclude dividends, fees and corporate-action reconciliation. No accuracy rankings or trading recommendations."}
