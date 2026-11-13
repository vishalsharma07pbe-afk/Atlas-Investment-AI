"""Fail-closed provider readiness checks; no external requests or token disclosure."""
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    access_token: str | None
    automatic_refresh: bool
    licensed_data_access: bool
    entitlement_confirmed: bool
    rate_per_second: float

def provider_readiness(config: ProviderConfig) -> dict:
    provider=config.provider.upper()
    reasons=[]
    if provider not in ("MANUAL_CSV","UPSTOX"):
        reasons.append("UNSUPPORTED_PROVIDER")
    if provider=="MANUAL_CSV":
        reasons.append("MANUAL_IMPORT_ONLY")
    if provider=="UPSTOX":
        if not config.access_token or not config.access_token.strip():
            reasons.append("MISSING_ACCESS_TOKEN")
        if not config.licensed_data_access:
            reasons.append("DATA_USAGE_RIGHTS_NOT_CONFIRMED")
        if not config.entitlement_confirmed:
            reasons.append("MARKET_DATA_ENTITLEMENT_NOT_CONFIRMED")
    if not 0<config.rate_per_second<=5:
        reasons.append("INVALID_RATE_LIMIT")
    if not config.automatic_refresh:
        reasons.append("AUTOMATIC_REFRESH_DISABLED")
    # Readiness is necessary but not sufficient: no upstream provider adapter
    # has been independently verified to support production collection.
    reasons.append("LIVE_PROVIDER_ADAPTER_NOT_VERIFIED")
    return {
        "provider":provider,
        "status":"NOT_READY",
        "automatic_collection_enabled":False,
        "automatic_refresh_requested":config.automatic_refresh,
        "credentials_present":bool(config.access_token and config.access_token.strip()) if provider=="UPSTOX" else False,
        "usage_rights_confirmed":config.licensed_data_access,
        "entitlement_confirmed":config.entitlement_confirmed,
        "blockers":sorted(set(reasons)),
        "notice":"No provider requests were made. No credentials are returned. Provider configuration alone does not establish live market-data access.",
    }
