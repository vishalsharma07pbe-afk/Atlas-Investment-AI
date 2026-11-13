"""Credential-safe configuration. Provider collection is disabled by default."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    backend_url: str = os.getenv("ATLAS_BACKEND_URL", "http://backend:8080")
    provider: str = os.getenv("MARKET_DATA_PROVIDER", "MANUAL_CSV").upper()
    upstox_token: str | None = os.getenv("UPSTOX_ACCESS_TOKEN")
    automatic_refresh: bool = os.getenv("MARKET_DATA_AUTO_REFRESH", "false").lower() == "true"
    request_rate_per_second: float = float(os.getenv("MARKET_DATA_RATE_PER_SECOND", "1"))
    licensed_data_access: bool = os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED", "false").lower() == "true"
    entitlement_confirmed: bool = os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED", "false").lower() == "true"

settings = Settings()
