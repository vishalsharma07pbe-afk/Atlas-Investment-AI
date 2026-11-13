"""Opt-in Upstox V3 daily historical candle preview; never persists market data."""
import json
import re
from datetime import date,datetime
from math import isfinite
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,build_opener,HTTPRedirectHandler
from fastapi import HTTPException
from .config import settings

KEY=re.compile(r"^(NSE_EQ|BSE_EQ)\|[A-Z0-9]{6,24}$")

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None

def preview_daily(instrument_key:str,from_date:date,to_date:date):
    if settings.provider!="UPSTOX" or not settings.licensed_data_access or not settings.entitlement_confirmed:
        raise HTTPException(status_code=403,detail="Provider and data usage entitlement must be explicitly configured")
    token=settings.upstox_token
    if not token or not token.strip():
        raise HTTPException(status_code=503,detail="Provider credential unavailable")
    if not KEY.fullmatch(instrument_key):
        raise HTTPException(status_code=422,detail="Unsupported equity instrument key")
    if to_date<from_date or to_date>date.today() or (to_date-from_date).days>366:
        raise HTTPException(status_code=422,detail="Date range must be historical and at most 366 days")
    url="https://api.upstox.com/v3/historical-candle/"+quote(instrument_key,safe="")+"/days/1/"+to_date.isoformat()+"/"+from_date.isoformat()
    request=Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/json"})
    try:
        # Redirects are rejected to prevent sending bearer credentials to another host.
        with build_opener(NoRedirect()).open(request,timeout=8) as response:
            if response.status!=200:
                raise HTTPException(status_code=502,detail="Provider returned unexpected status")
            body=response.read(2_000_001)
            if len(body)>2_000_000:
                raise HTTPException(status_code=502,detail="Provider payload too large")
        payload=json.loads(body)
        if payload.get("status")!="success" or not isinstance(payload.get("data",{}).get("candles"),list):
            raise ValueError("Invalid provider envelope")
        output=[]
        for row in payload["data"]["candles"]:
            if not isinstance(row,list) or len(row)<6:
                raise ValueError("Invalid candle shape")
            stamp=datetime.fromisoformat(row[0])
            if stamp.tzinfo is None:
                raise ValueError("Timezone required")
            day=stamp.date()
            o,h,l,c=[float(v) for v in row[1:5]]
            volume=row[5]
            if isinstance(volume,bool) or not isinstance(volume,int) or volume<0:
                raise ValueError("Invalid volume")
            if not all(isfinite(v) for v in (o,h,l,c)) or l<=0 or l>min(o,c) or h<max(o,c):
                raise ValueError("Invalid OHLC")
            if not from_date<=day<=to_date:
                raise ValueError("Out-of-range candle")
            output.append({"trade_date":day.isoformat(),"open":o,"high":h,"low":l,
                           "close":c,"volume":volume,"source":"UPSTOX_V3",
                           "adjustment_status":"UNVERIFIED"})
        if len(output)>500 or len({x["trade_date"] for x in output})!=len(output):
            raise ValueError("Excessive or duplicate candles")
        output.sort(key=lambda x:x["trade_date"])
        return {"status":"PREVIEW_ONLY","instrument_key":instrument_key,
                "source":"UPSTOX_V3","candle_count":len(output),"candles":output,
                "notice":"Provider-sourced historical preview only. Adjustment status, exchange-session mapping and ingestion rights are not independently verified. Not persisted or eligible for signals."}
    except HTTPError as exc:
        if exc.code in (401,403):
            raise HTTPException(status_code=502,detail="Provider authentication or entitlement rejected") from None
        if exc.code==429:
            raise HTTPException(status_code=503,detail="Provider rate limit reached; retry later") from None
        raise HTTPException(status_code=502,detail="Provider request failed") from None
    except (URLError,TimeoutError,OSError):
        raise HTTPException(status_code=503,detail="Provider unavailable") from None
    except (ValueError,TypeError,KeyError,json.JSONDecodeError):
        raise HTTPException(status_code=502,detail="Provider returned invalid candle data") from None
