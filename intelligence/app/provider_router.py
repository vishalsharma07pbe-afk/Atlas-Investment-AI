"""Provider-independent, read-only failover with bounded attempts and explicit freshness.
No remote network clients are configured by this module.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from threading import RLock
from time import monotonic
from typing import Callable
from decimal import Decimal, InvalidOperation
import re

@dataclass(frozen=True)
class Quote:
    symbol: str
    price: str
    observed_at: datetime
    provider: str
    asset_type: str = "EQUITY"

class ProviderFailure(Exception):
    pass

class CircuitBreaker:
    def __init__(self, threshold=3, cooldown_seconds=60, clock=monotonic):
        self.threshold=threshold
        self.cooldown_seconds=cooldown_seconds
        self.clock=clock
        self._lock=RLock()
        self._states={}
    def allow(self, name):
        with self._lock:
            failures, until=self._states.get(name,(0,0))
            return self.clock()>=until
    def success(self, name):
        with self._lock: self._states.pop(name,None)
    def failure(self, name):
        with self._lock:
            failures,until=self._states.get(name,(0,0))
            failures=(1 if until>0 and self.clock()>=until else failures+1) if self.clock()>=until else failures
            self._states[name]=(failures,self.clock()+self.cooldown_seconds if failures>=self.threshold else 0)
    def status(self, name):
        with self._lock:
            failures,until=self._states.get(name,(0,0))
            return {"provider":name,"state":"OPEN" if self.clock()<until else "CLOSED","failures":failures}

def validate_quote(quote, symbol, max_age_seconds, now):
    if not isinstance(quote,Quote) or quote.symbol!=symbol or quote.asset_type!="EQUITY":
        raise ProviderFailure("INSTRUMENT_MISMATCH")
    if quote.observed_at.tzinfo is None or quote.observed_at.utcoffset() is None:
        raise ProviderFailure("NAIVE_TIMESTAMP")
    age=(now-quote.observed_at.astimezone(timezone.utc)).total_seconds()
    if age<0 or age>max_age_seconds:
        raise ProviderFailure("STALE_OR_FUTURE")
    try:
        price=Decimal(quote.price)
    except (InvalidOperation,ValueError,TypeError):
        raise ProviderFailure("INVALID_PRICE") from None
    if not price.is_finite() or price<=0:
        raise ProviderFailure("INVALID_PRICE")
    return quote

class ReadOnlyRouter:
    def __init__(self, adapters, breaker=None, clock=lambda:datetime.now(timezone.utc)):
        # adapters: ordered (name, callable, entitlement_confirmed) tuples
        self.adapters=list(adapters)
        self.breaker=breaker or CircuitBreaker()
        self.clock=clock
    def quote(self, symbol, max_age_seconds=60):
        if not re.fullmatch(r"[A-Z0-9._&-]{1,40}",symbol):
            raise ValueError("INVALID_SYMBOL")
        if not 1<=max_age_seconds<=86400:
            raise ValueError("INVALID_MAX_AGE")
        attempted=[]
        for name,fetch,authorized in self.adapters:
            if not authorized:
                attempted.append({"provider":name,"status":"BLOCKED_ENTITLEMENT"})
                continue
            if not self.breaker.allow(name):
                attempted.append({"provider":name,"status":"CIRCUIT_OPEN"})
                continue
            try:
                quote=validate_quote(fetch(symbol),symbol,max_age_seconds,self.clock())
            except Exception:
                self.breaker.failure(name)
                attempted.append({"provider":name,"status":"FAILED_OR_INVALID"})
                continue
            self.breaker.success(name)
            return {"status":"VALIDATED","live":False,"quote":{"symbol":quote.symbol,"price":quote.price,
                "observed_at":quote.observed_at.isoformat(),"source":name,"freshness":"WITHIN_REQUESTED_AGE"},
                "attempts":attempted}
        return {"status":"UNAVAILABLE","live":False,"quote":None,"attempts":attempted,
                "notice":"No authorized provider supplied a fresh validated quote. Never treat cached data as live."}

def readiness():
    # No remote adapters are enabled until credentials, terms and ingestion are independently verified.
    return {"status":"SAFE_OFFLINE","automatic_live_failover_enabled":False,
        "router_capabilities":["ORDERED_FALLBACK","ENTITLEMENT_GATE","FRESHNESS_VALIDATION",
          "PRICE_VALIDATION","CIRCUIT_BREAKER","NO_TRADE_EXECUTION"],
        "configured_adapters":0,"quote_available":False,
        "blockers":["LICENSED_PRIMARY_FEED_NOT_ACTIVATED","AUTHORIZED_BACKUP_FEED_NOT_CONFIGURED"],
        "notice":"Failover engine is implemented and tested with injected adapters; no live data collection is enabled."}
