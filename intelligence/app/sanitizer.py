"""Strict public-indicator payload; no broker balances, credentials, or arbitrary text."""
import math
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .ai_failover import _safe_payload

SYMBOL=re.compile(r"^[A-Z0-9._&-]{1,40}$")

class AllowlistedAnalysisPayload(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    symbol: str
    market: str = "NSE"
    price_change_pct: float | None = Field(default=None,ge=-100,le=10000)
    volume_change_pct: float | None = Field(default=None,ge=-100,le=100000)
    sector: str | None = Field(default=None,max_length=100)
    technical_summary: str | None = Field(default=None,max_length=600)
    news_summary: str | None = Field(default=None,max_length=600)

    @field_validator("symbol")
    @classmethod
    def valid_symbol(cls,v):
        if not SYMBOL.fullmatch(v):
            raise ValueError("INVALID_SYMBOL")
        return v

    @field_validator("market")
    @classmethod
    def valid_market(cls,v):
        if v not in ("NSE","BSE","US"):
            raise ValueError("INVALID_MARKET")
        return v

    @field_validator("price_change_pct","volume_change_pct")
    @classmethod
    def finite(cls,v):
        if v is not None and not math.isfinite(v):
            raise ValueError("NONFINITE_INDICATOR")
        return v

def build_payload(symbol, observations):
    if not isinstance(observations,dict):
        raise ValueError("INVALID_OBSERVATIONS")
    # Explicit rejection rather than silently filtering leaked portfolio or token fields.
    data=AllowlistedAnalysisPayload.model_validate({"symbol":symbol,**observations})
    return _safe_payload(data.model_dump(exclude_none=True))
