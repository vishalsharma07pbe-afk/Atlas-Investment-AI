"""Daily refresh of Upstox's documented public mutual-fund instrument snapshot."""
from __future__ import annotations
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
import json
import os
import re
import httpx

from . import nav_catalog

SOURCE = "UPSTOX_MF_INSTRUMENTS"
URL = "https://assets.upstox.com/market-quote/instruments/exchange/mf-instruments.json.gz"
IST = timezone(timedelta(hours=5,minutes=30))
MAX_COMPRESSED_BYTES = 25_000_000
MAX_DECOMPRESSED_BYTES = 100_000_000
MAX_ROWS = 150_000
KEY = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

def config(environ=None):
    env = os.environ if environ is None else environ
    enabled = env.get("ATLAS_MF_NAV_AUTO_REFRESH_ENABLED","false").lower() == "true"
    return {"enabled":enabled,"source":SOURCE,"schedule":"06:30 Asia/Kolkata",
            "url":URL,"requires_upstox_account":False}

def parse_snapshot(payload: bytes, observed_on: date | None = None):
    if len(payload)>MAX_COMPRESSED_BYTES:
        raise ValueError("MF_SNAPSHOT_TOO_LARGE")
    try:
        raw = gzip.decompress(payload) if payload[:2] == b"\x1f\x8b" else payload
    except (gzip.BadGzipFile,EOFError):
        raise ValueError("MF_SNAPSHOT_INVALID_GZIP") from None
    if len(raw)>MAX_DECOMPRESSED_BYTES:
        raise ValueError("MF_SNAPSHOT_TOO_LARGE")
    try:
        data=json.loads(raw)
    except (UnicodeDecodeError,json.JSONDecodeError):
        raise ValueError("MF_SNAPSHOT_INVALID_JSON") from None
    if not isinstance(data,list) or len(data)>MAX_ROWS:
        raise ValueError("MF_SNAPSHOT_INVALID_ROOT")
    records={};invalid=0;today=datetime.now(IST).date();observed_on=observed_on or today
    for item in data:
        try:
            if not isinstance(item,dict): raise ValueError()
            key=str(item.get("instrument_key","")).strip().upper()
            name=str(item.get("name","")).strip()
            nav=Decimal(str(item.get("last_price","")))
            supplied_date=item.get("last_price_date")
            nav_date=date.fromisoformat(str(supplied_date)) if supplied_date else observed_on
            date_status="DECLARED" if supplied_date else "PROVIDER_NOT_SUPPLIED"
            if not KEY.fullmatch(key) or not name or len(name)>300: raise ValueError()
            if not nav.is_finite() or nav<=0 or nav>Decimal("1000000000"): raise ValueError()
            if nav_date>today or key in records: raise ValueError()
            records[key]={"provider_key":key,"scheme_name":name,"nav":str(nav),
                          "nav_date":nav_date.isoformat(),"nav_date_status":date_status,"metadata":{
                            "observed_on":observed_on.isoformat(),"nav_date_status":date_status,
                            "amc":item.get("amc"),"scheme_type":item.get("scheme_type"),
                            "plan":item.get("plan"),"dividend_type":item.get("dividend_type"),
                            "purchase_allowed":item.get("purchase_allowed"),
                            "redemption_allowed":item.get("redemption_allowed"),
                            "minimum_purchase_amount":item.get("minimum_purchase_amount"),
                            "additional_purchase_amount":item.get("additional_purchase_amount"),
                            "minimum_redemption_amount":item.get("minimum_redemption_amount"),
                            "minimum_redemption_quantity":item.get("minimum_redemption_quantity"),
                            "settlement_type":item.get("settlement_type"),
                            "hair_cut":item.get("hair_cut")}}
        except (ValueError,InvalidOperation,TypeError): invalid+=1
    if not records: raise ValueError("NO_VALID_MF_NAV_RECORDS")
    return list(records.values()),invalid

def refresh_once(client=None):
    started=datetime.now(timezone.utc).isoformat()
    own=client is None
    client=client or httpx.Client(timeout=45,follow_redirects=True,
                                  headers={"User-Agent":"ATLAS-Personal-Research/1.0"})
    try:
        response=client.get(URL)
        response.raise_for_status()
        records,invalid=parse_snapshot(response.content)
        result=nav_catalog.import_provider_snapshot(records,SOURCE)
        result["invalid_rows"]=invalid
        nav_catalog.record_refresh_run(started,SOURCE,"SUCCESS",result["parsed"],invalid,
                                       result["inserted_history_rows"])
        return result
    except (httpx.HTTPError,ValueError) as exc:
        code=str(exc) if isinstance(exc,ValueError) else "MF_PROVIDER_UNAVAILABLE"
        nav_catalog.record_refresh_run(started,SOURCE,"FAILED",error_code=code)
        raise RuntimeError(code) from None
    finally:
        if own: client.close()

def _seconds_until_next(now=None):
    now=now or datetime.now(IST)
    target=now.replace(hour=6,minute=30,second=0,microsecond=0)
    if target<=now: target+=timedelta(days=1)
    return max(1,(target-now).total_seconds()),target

class NavRefreshScheduler:
    def __init__(self):
        self.task=None;self.runs=0;self.last_error=None;self.next_run_at=None
    async def start(self):
        if config()["enabled"] and self.task is None:
            self.task=asyncio.create_task(self._loop())
    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
            self.task=None
    async def _run(self):
        try:
            await asyncio.to_thread(refresh_once);self.runs+=1;self.last_error=None
        except RuntimeError as exc: self.last_error=str(exc)
    async def _loop(self):
        # Populate an empty catalog immediately; subsequent attempts follow the daily cadence.
        if nav_catalog.catalog_status()["scheme_count"] == 0: await self._run()
        while True:
            seconds,target=_seconds_until_next();self.next_run_at=target.isoformat()
            await asyncio.sleep(seconds);await self._run()
    def status(self):
        return {**config(),"running":self.task is not None and not self.task.done(),
                "completed_runs":self.runs,"last_error_code":self.last_error,
                "next_run_at":self.next_run_at}

scheduler=NavRefreshScheduler()
