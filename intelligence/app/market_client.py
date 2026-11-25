import json
import os
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from fastapi import HTTPException
from .config import settings
from .fund_categories import CATEGORIES

def _internal_path(path:str)->str:
    if path.startswith("/api/v1/market-data/discovery-universe?"):
        return "/api/v1/internal/feed/discovery-universe?"+path.split("?",1)[1]
    if path.startswith("/api/v1/market-data/discovery-candles?"):
        return "/api/v1/internal/feed/discovery-candles?"+path.split("?",1)[1]
    if path.startswith("/api/v1/market-data/instruments/"):
        return "/api/v1/internal/feed/instruments/"+path.removeprefix("/api/v1/market-data/instruments/")
    if path.startswith("/api/v1/instruments"):
        return "/api/v1/internal/feed/instruments"+path.removeprefix("/api/v1/instruments")
    if path.startswith("/api/v1/mutual-funds/historical-watch?category="):
        category = path.removeprefix("/api/v1/mutual-funds/historical-watch?category=")
        if category in CATEGORIES:
            return "/api/v1/internal/feed/fund-history?category="+category
    if path == "/api/v1/portfolio-research-identities":
        return "/api/v1/internal/feed/portfolio-research-identities"
    if path == "/api/v1/market-data/strategy-benchmark":
        return "/api/v1/internal/feed/strategy-benchmark"
    if path in ("/api/v1/market-data/strategy-calendar?exchange=NSE","/api/v1/market-data/strategy-calendar?exchange=BSE"):
        return "/api/v1/internal/feed/strategy-calendar?"+path.split("?",1)[1]
    if path == "/api/v1/market-data/session-context":
        return "/api/v1/internal/feed/session-context"
    if path == "/api/v1/data-health/summary":
        return "/api/v1/internal/feed/data-health/summary"
    raise HTTPException(status_code=500,detail="Unsupported internal market-data route")

def backend_json(path:str):
    token=os.getenv("INTERNAL_SERVICE_TOKEN","")
    if not token:
        raise HTTPException(status_code=503,detail="Internal market-data credential is not configured")
    try:
        headers={"Accept":"application/json","X-Atlas-Service-Token":token}
        with urlopen(Request(settings.backend_url+_internal_path(path),headers=headers),timeout=10) as response:
            payload=response.read(8_000_001)
            if len(payload)>8_000_000:raise ValueError("response too large")
            return json.loads(payload)
    except HTTPError as exc: raise HTTPException(status_code=exc.code if exc.code in (404,422) else 502,detail="Market-data backend rejected request") from exc
    except (URLError,TimeoutError,OSError,ValueError,json.JSONDecodeError) as exc: raise HTTPException(status_code=503,detail="Market-data backend unavailable or invalid") from exc
