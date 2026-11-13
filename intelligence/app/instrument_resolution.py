"""Resolve verified exchange registry records to Upstox V3 instrument keys.

Only NSE equity keys with validated ISINs can be derived safely. BSE keys
require authoritative provider mapping; never guess them from ticker names.
"""
import re
from typing import Any
from .upstox_stream import StreamPolicy,subscription_request

_ISIN=re.compile(r"^IN[A-Z0-9]{10}$")

def resolve_upstox_instrument(record: dict[str,Any]) -> dict:
    exchange=str(record.get("exchange") or "").upper()
    symbol=str(record.get("symbol") or "")
    isin=str(record.get("isin") or "").upper()
    active=record.get("active") is True
    status=str(record.get("listing_status") or "").upper()
    result={"exchange":exchange,"symbol":symbol,"isin":isin or None,
            "provider":"UPSTOX","instrument_key":None,"subscription_ready":False}
    if not active or status not in ("ACTIVE","LISTED"):
        result["blocker"]="INSTRUMENT_NOT_VERIFIED_ACTIVE"
    elif exchange!="NSE":
        result["blocker"]="PROVIDER_INSTRUMENT_MAPPING_REQUIRED"
    elif not _ISIN.fullmatch(isin):
        result["blocker"]="VALID_INDIAN_ISIN_REQUIRED"
    else:
        result["instrument_key"]="NSE_EQ|"+isin
        result["subscription_ready"]=True
        result["blocker"]=None
    return result

def make_subscription(record:dict[str,Any],guid:str)->dict:
    resolution=resolve_upstox_instrument(record)
    if not resolution["subscription_ready"]:
        raise ValueError(resolution["blocker"])
    return subscription_request([resolution["instrument_key"]],StreamPolicy(),guid)
