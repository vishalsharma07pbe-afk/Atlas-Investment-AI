import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from fastapi import HTTPException
from .config import settings

def backend_json(path:str):
    try:
        with urlopen(Request(settings.backend_url+path,headers={"Accept":"application/json"}),timeout=10) as response:
            payload=response.read(8_000_001)
            if len(payload)>8_000_000:raise ValueError("response too large")
            return json.loads(payload)
    except HTTPError as exc: raise HTTPException(status_code=exc.code if exc.code in (404,422) else 502,detail="Market-data backend rejected request") from exc
    except (URLError,TimeoutError,OSError,ValueError,json.JSONDecodeError) as exc: raise HTTPException(status_code=503,detail="Market-data backend unavailable or invalid") from exc
