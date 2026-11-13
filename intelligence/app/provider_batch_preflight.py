"""Fail-closed dry-run gate for prospective licensed daily market-data batches.

No provider requests, credentials, database writes, or trading actions.
"""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

class ProviderCandle(BaseModel):
    instrument_key: str = Field(min_length=1,max_length=120,pattern=r"^[A-Za-z0-9|:_-]+$")
    trade_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    @model_validator(mode="after")
    def valid_ohlc(self):
        if self.high < max(self.open,self.close,self.low) or self.low > min(self.open,self.close,self.high):
            raise ValueError("OHLC bounds inconsistent")
        if self.trade_date>date.today():
            raise ValueError("Future trade date")
        return self

class BatchPreflightRequest(BaseModel):
    provider: str = Field(min_length=1,max_length=60)
    source_reference: str = Field(min_length=3,max_length=240)
    rights_confirmed: bool = False
    entitlement_confirmed: bool = False
    instrument_mapping_confirmed: bool = False
    candles: list[ProviderCandle] = Field(min_length=1,max_length=2000)

def preflight_batch(request: BatchPreflightRequest, today: date | None=None) -> dict:
    today=today or date.today()
    blockers=[]
    if request.provider.upper()!="UPSTOX":blockers.append("UNSUPPORTED_PROVIDER")
    if not request.rights_confirmed:blockers.append("DATA_USAGE_RIGHTS_UNCONFIRMED")
    if not request.entitlement_confirmed:blockers.append("MARKET_DATA_ENTITLEMENT_UNCONFIRMED")
    if not request.instrument_mapping_confirmed:blockers.append("INSTRUMENT_MAPPING_UNCONFIRMED")
    seen=set()
    by_instrument={}
    for candle in request.candles:
        key=(candle.instrument_key,candle.trade_date)
        if key in seen:blockers.append("DUPLICATE_INSTRUMENT_DATE")
        seen.add(key)
        by_instrument.setdefault(candle.instrument_key,[]).append(candle.trade_date)
    newest=max(c.trade_date for c in request.candles)
    if (today-newest).days>3:blockers.append("STALE_BATCH_OVER_3_CALENDAR_DAYS")
    if any((today-d).days<0 for dates in by_instrument.values() for d in dates):
        blockers.append("FUTURE_DATE")
    if any(len(dates)!=len(set(dates)) for dates in by_instrument.values()):
        blockers.append("DUPLICATE_INSTRUMENT_DATE")
    if any((today-max(dates)).days>3 for dates in by_instrument.values()):
        blockers.append("STALE_INSTRUMENT_OVER_3_CALENDAR_DAYS")
    # Calendar-day threshold is intentionally conservative around weekends/holidays.
    # Passing this contract is not permission to collect or ingest provider data.
    blockers.append("PROVIDER_ADAPTER_NOT_VERIFIED")
    return {"status":"BLOCKED","ingestion_authorized":False,"dry_run":True,
            "records_examined":len(request.candles),"instruments_examined":len(by_instrument),
            "latest_trade_date":newest.isoformat(),"blockers":sorted(set(blockers)),
            "notice":"Dry-run only. No external feed was contacted or data persisted. Confirm licensed access, official trading calendar, verified adapter and backend ingestion before enabling collection."}
