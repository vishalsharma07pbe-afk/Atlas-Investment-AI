"""Bounded, synchronous provider batch review. Never stores or qualifies unverified candles."""
from datetime import date,datetime,timedelta,timezone
from time import monotonic,sleep
from pydantic import BaseModel,Field,model_validator
from fastapi import HTTPException
from .config import settings
from .upstox_preview import preview_daily,KEY

class BatchRequest(BaseModel):
    instrument_keys:list[str]=Field(min_length=1,max_length=5)
    from_date:date
    to_date:date
    max_age_days:int=Field(default=7,ge=0,le=30)

    @model_validator(mode="after")
    def validate_batch(self):
        if len(set(self.instrument_keys))!=len(self.instrument_keys):
            raise ValueError("Duplicate instrument keys")
        if any(not KEY.fullmatch(key) for key in self.instrument_keys):
            raise ValueError("Only NSE/BSE equity instrument keys are supported")
        if self.to_date<self.from_date or self.to_date>date.today() or (self.to_date-self.from_date).days>366:
            raise ValueError("Invalid historical date range")
        return self

def review_batch(request:BatchRequest,fetch=preview_daily,now=None,clock=monotonic,pause=sleep):
    """Calls each approved provider key at most once; never retries or polls."""
    if settings.provider!="UPSTOX" or not settings.licensed_data_access or not settings.entitlement_confirmed or not settings.upstox_token:
        raise HTTPException(status_code=403,detail="Provider access and entitlement not configured")
    rate=settings.request_rate_per_second
    if not 0<rate<=5:
        raise HTTPException(status_code=503,detail="Invalid provider request rate configuration")
    today=now or date.today()
    results=[]
    previous_start=None
    for key in request.instrument_keys:
        if previous_start is not None:
            delay=1/rate-(clock()-previous_start)
            if delay>0:pause(delay)
        previous_start=clock()
        try:
            preview=fetch(key,request.from_date,request.to_date)
            candles=preview["candles"]
            if not isinstance(candles,list) or len(candles)>500:
                raise ValueError("Invalid provider candles")
            latest=date.fromisoformat(candles[-1]["trade_date"]) if candles else None
            age=(today-latest).days if latest else None
            flags=["ADJUSTMENT_UNVERIFIED","EXCHANGE_SESSION_MAPPING_UNVERIFIED",
                   "PROVIDER_TO_LOCAL_INSTRUMENT_MAPPING_UNVERIFIED"]
            if not candles:flags.append("NO_CANDLES")
            if age is not None and (age<0 or age>request.max_age_days):
                flags.append("STALE_OR_FUTURE_CANDLES")
            # Never return raw candles from a multi-instrument review.
            results.append({"instrument_key":key,"status":"REVIEW_REQUIRED",
                "candle_count":len(candles),"latest_trade_date":latest.isoformat() if latest else None,
                "age_calendar_days":age,"quality_flags":flags})
        except (HTTPException,ValueError,TypeError,KeyError,IndexError):
            results.append({"instrument_key":key,"status":"PROVIDER_ERROR",
                "candle_count":0,"latest_trade_date":None,"age_calendar_days":None,
                "quality_flags":["PROVIDER_REQUEST_FAILED_OR_INVALID"]})
    return {"status":"REVIEW_ONLY","source":"UPSTOX_V3","requested":len(request.instrument_keys),
        "succeeded":sum(r["status"]=="REVIEW_REQUIRED" for r in results),
        "failed":sum(r["status"]=="PROVIDER_ERROR" for r in results),
        "results":results,"automatic_ingestion_enabled":False,
        "notice":"On-demand bounded provider quality review. No data persisted, no live feed, no verified adjustment or trading signals. Entitlement declarations are operator-supplied."}
