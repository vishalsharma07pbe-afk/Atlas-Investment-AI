"""Read-only, provider-independent local research hub. No unapproved network collection."""
from datetime import datetime, timezone, date
from typing import Literal
from pydantic import BaseModel, Field
from . import nav_catalog
from .config import settings

class Source(BaseModel):
    code: str
    datasets: list[str]
    transport: Literal["LOCAL", "REMOTE"]
    authorized: bool
    state: Literal["AVAILABLE_LOCAL", "BLOCKED_AUTHORIZATION", "NOT_CONFIGURED"]
    live: bool = False

class Observation(BaseModel):
    symbol: str
    asset_type: Literal["MUTUAL_FUND"]
    value: str
    observed_at: str
    source: str
    freshness: Literal["EOD", "STALE"]
    live: bool = False

def sources():
    remote_authorized = bool(settings.licensed_data_access and settings.entitlement_confirmed and settings.upstox_token)
    return [
        Source(code="AMFI_MANUAL",datasets=["MUTUAL_FUND_NAV"],transport="LOCAL",authorized=True,state="AVAILABLE_LOCAL"),
        Source(code="UPSTOX",datasets=["EQUITY_QUOTE","EQUITY_CANDLE"],transport="REMOTE",
               authorized=remote_authorized,state="NOT_CONFIGURED" if remote_authorized else "BLOCKED_AUTHORIZATION"),
        Source(code="ALTERNATIVE_EQUITY",datasets=["EQUITY_QUOTE","EQUITY_CANDLE"],transport="REMOTE",
               authorized=False,state="BLOCKED_AUTHORIZATION"),
    ]

def _freshness(day: str):
    try:
        age=(datetime.now(timezone.utc).date()-date.fromisoformat(day)).days
        return "EOD" if 0<=age<=4 else "STALE"
    except (TypeError, ValueError):
        return "STALE"

def lookup(query: str, asset_type: str):
    query=query.strip()
    if not query or len(query)>100:
        raise ValueError("INVALID_QUERY")
    if asset_type=="MUTUAL_FUND":
        result=nav_catalog.search_schemes(query)
        observations=[Observation(symbol=str(x["scheme_code"]),asset_type="MUTUAL_FUND",
             value=str(x["nav"]),observed_at=str(x["nav_date"]),source=str(x["source"]),
             freshness=_freshness(str(x["nav_date"]))) for x in result["items"]]
        return {"query":query,"asset_type":asset_type,"items":[x.model_dump() for x in observations],
                "status":"LOCAL_EOD" if observations else "NO_VALIDATED_DATA","live":False}
    if asset_type=="EQUITY":
        return {"query":query,"asset_type":asset_type,"items":[],"status":"NO_AUTHORIZED_EQUITY_FEED",
                "live":False,"notice":"No equity price is returned without verified authorized ingestion."}
    raise ValueError("UNSUPPORTED_ASSET_TYPE")

def health():
    return {"checked_at":datetime.now(timezone.utc).isoformat(),"sources":[s.model_dump() for s in sources()],
            "automatic_failover_enabled":False,"live_feed_verified":False,
            "notice":"Only local manual NAV snapshots are queried. Remote adapters are intentionally blocked pending authorization."}
