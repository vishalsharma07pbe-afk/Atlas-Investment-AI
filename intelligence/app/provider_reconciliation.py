"""Provider-to-registry reconciliation. No persistence or implicit trust in provider prices."""
from datetime import date
from math import isfinite
from pydantic import BaseModel,Field,model_validator

class Mapping(BaseModel):
    instrument_key:str=Field(min_length=8,max_length=40)
    exchange:str
    symbol:str=Field(min_length=1,max_length=50)
    series:str=Field(min_length=1,max_length=20)
    isin:str=Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    adjustment_verified:bool=False
    sessions_verified:bool=False
    usage_rights_verified:bool=False

class Candle(BaseModel):
    trade_date:date
    open:float
    high:float
    low:float
    close:float
    volume:int=Field(ge=0)
    adjustment_status:str="UNVERIFIED"

    @model_validator(mode="after")
    def valid(self):
        prices=(self.open,self.high,self.low,self.close)
        if not all(isfinite(p) for p in prices) or self.low<=0 or self.low>min(self.open,self.close) or self.high<max(self.open,self.close):
            raise ValueError("Invalid OHLC")
        return self

class ReconciliationRequest(BaseModel):
    mapping:Mapping
    candles:list[Candle]=Field(min_length=1,max_length=500)
    known_session_dates:list[date]=Field(default_factory=list,max_length=500)
    registry_exchange:str
    registry_symbol:str
    registry_series:str
    registry_isin:str
    provider_source_revision:str=Field(min_length=1,max_length=80)

def reconcile(request:ReconciliationRequest,as_of=None):
    """Independent explicit checks; never auto-certify source data or return import-ready CSV."""
    m=request.mapping
    blockers=[]
    expected_exchange=m.instrument_key.split("|",1)[0].split("_",1)[0]
    if m.instrument_key.count("|")!=1 or expected_exchange not in ("NSE","BSE") or m.exchange!=expected_exchange:
        blockers.append("PROVIDER_EXCHANGE_KEY_MISMATCH")
    if (m.exchange,m.symbol,m.series,m.isin)!=(request.registry_exchange,request.registry_symbol,request.registry_series,request.registry_isin):
        blockers.append("REGISTRY_MAPPING_MISMATCH")
    dates=[x.trade_date for x in request.candles]
    if len(set(dates))!=len(dates):blockers.append("DUPLICATE_CANDLE_DATE")
    if dates!=sorted(dates):blockers.append("UNSORTED_CANDLES")
    if any(d>(as_of or date.today()) for d in dates):blockers.append("FUTURE_CANDLES")
    if not m.usage_rights_verified:blockers.append("USAGE_RIGHTS_NOT_VERIFIED")
    if not m.adjustment_verified:blockers.append("CORPORATE_ACTION_ADJUSTMENT_NOT_VERIFIED")
    if not m.sessions_verified:blockers.append("EXCHANGE_SESSIONS_NOT_VERIFIED")
    if any(c.adjustment_status not in ("RAW_UNADJUSTED","ADJUSTED") for c in request.candles):
        blockers.append("CANDLE_ADJUSTMENT_UNVERIFIED")
    if len({c.adjustment_status for c in request.candles})!=1:
        blockers.append("MIXED_ADJUSTMENT_STATUS")
    known=set(request.known_session_dates)
    missing=sorted(set(dates)-known)
    if missing:blockers.append("MISSING_VERIFIED_SESSION_DATES")
    # User-supplied booleans and session dates are declarations, not third-party proof.
    blockers.append("INDEPENDENT_PROVENANCE_AUDIT_REQUIRED")
    return {"status":"BLOCKED_FROM_AUTOMATIC_INGESTION","blockers":sorted(set(blockers)),
        "instrument_key":m.instrument_key,"mapped_instrument":{"exchange":m.exchange,"symbol":m.symbol,"series":m.series},
        "candles_reviewed":len(dates),"first_date":min(dates).isoformat(),"last_date":max(dates).isoformat(),
        "unmatched_session_dates":[d.isoformat() for d in missing[:30]],
        "unmatched_session_count":len(missing),"source_revision":request.provider_source_revision,
        "notice":"Reconciliation preview only. Declarations do not verify source rights, corporate actions or exchange sessions. No import file or database write is produced."}
