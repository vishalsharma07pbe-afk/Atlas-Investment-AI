"""Authenticated Upstox V3 adapter. It is inert unless explicitly configured.

The adapter does not place orders, bypass authentication, or call exchange websites.
Returned data still must pass the Spring ingestion quality gate before persistence.
"""
from datetime import date
import json, time
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ..upstox_http_identity import USER_AGENT

class ProviderError(RuntimeError): pass

class UpstoxHistoricalProvider:
    base_url = "https://api.upstox.com"
    def __init__(self, token: str, rate_per_second: float = 1.0, retries: int = 3):
        if not token: raise ValueError("UPSTOX_ACCESS_TOKEN is required")
        self.token=token; self.interval=1/max(0.1,min(rate_per_second,10)); self.retries=max(0,min(retries,5)); self.last=0.0

    def daily(self, instrument_key: str, start: date, end: date) -> list[dict]:
        if not instrument_key or "|" not in instrument_key: raise ValueError("A documented Upstox instrument key is required")
        path=f"/v3/historical-candle/{quote(instrument_key,safe='')}/days/1/{end.isoformat()}/{start.isoformat()}"
        payload=self._get(path); candles=payload.get("data",{}).get("candles",[])
        result=[]
        for row in candles:
            if not isinstance(row,list) or len(row)<6: raise ProviderError("Provider returned an invalid candle row")
            result.append({"timestamp":row[0],"open":row[1],"high":row[2],"low":row[3],"close":row[4],"volume":row[5],"adjustment_status":"RAW_UNADJUSTED"})
        return result

    def _get(self,path:str)->dict:
        for attempt in range(self.retries+1):
            wait=self.interval-(time.monotonic()-self.last)
            if wait>0: time.sleep(wait)
            request=Request(self.base_url+path,headers={"Accept":"application/json","User-Agent":USER_AGENT,"Authorization":"Bearer "+self.token})
            try:
                self.last=time.monotonic()
                with urlopen(request,timeout=15) as response:
                    if response.status!=200: raise ProviderError(f"Provider HTTP {response.status}")
                    return json.loads(response.read(5_000_000))
            except (HTTPError,URLError,TimeoutError,OSError,json.JSONDecodeError) as exc:
                if attempt>=self.retries: raise ProviderError("Upstox historical request failed after retries") from exc
                time.sleep(min(2**attempt,8))
        raise ProviderError("Unreachable")
