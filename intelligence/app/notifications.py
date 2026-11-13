"""Local, provenance-aware notification feed; no background external market polling."""
import json,os
from datetime import date,datetime,timezone
from pathlib import Path
from decimal import Decimal
from pydantic import BaseModel,Field,model_validator

class Alert(BaseModel):
    id:str=Field(pattern=r"^[a-zA-Z0-9_-]{3,80}$")
    category:str=Field(pattern=r"^(IPO_UPCOMING|IPO_SUBSCRIPTION|IPO_ALLOTMENT|MARKET_EVENT|CORPORATE_ACTION|RESEARCH_UPDATE|RISK_WARNING)$")
    title:str=Field(min_length=3,max_length=160)
    description:str=Field(min_length=1,max_length=1200)
    event_date:date|None=None
    published_at:datetime
    source_name:str=Field(min_length=2,max_length=100)
    source_url:str=Field(pattern=r"^https://[^\s]+$",max_length=1000)
    subscription_total_x:Decimal|None=Field(default=None,ge=0,le=100000)
    subscription_as_of:datetime|None=None

    @model_validator(mode="after")
    def check(self):
        if self.published_at.tzinfo is None:raise ValueError("published_at requires timezone")
        if self.published_at>datetime.now(timezone.utc):raise ValueError("Future publication time")
        if self.category=="IPO_SUBSCRIPTION":
            if self.subscription_total_x is None or self.subscription_as_of is None:
                raise ValueError("IPO subscription requires ratio and timestamp")
        if self.subscription_as_of is not None:
            if self.subscription_as_of.tzinfo is None or self.subscription_as_of>datetime.now(timezone.utc):
                raise ValueError("Invalid subscription as-of time")
            if self.subscription_as_of>self.published_at:
                raise ValueError("Subscription snapshot cannot postdate publication")
        return self

def _load():
    path=Path(os.getenv("ATLAS_ALERTS_FILE","/app/data/alerts.json"))
    try:
        if not path.is_file():return []
        if path.stat().st_size>1024*1024:raise ValueError("Alerts file exceeds 1MB")
        raw=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw,list) or len(raw)>200:raise ValueError("Invalid alerts collection")
        alerts=[Alert.model_validate(item) for item in raw]
        if len({a.id for a in alerts})!=len(alerts):raise ValueError("Duplicate alert IDs")
        return sorted(alerts,key=lambda a:a.published_at,reverse=True)
    except (OSError,ValueError,TypeError) as exc:
        # Never substitute invented alerts when local data is missing or invalid.
        raise RuntimeError("Notification source invalid or unavailable") from exc

def summary():
    alerts=_load()
    return {"status":"LOCAL_SOURCE_ONLY","ids":[a.id for a in alerts],
            "revision_keys":[a.id+"@"+a.published_at.isoformat() for a in alerts],
            "total":len(alerts),"live_feed_connected":False}

def details():
    alerts=_load()
    return {"status":"LOCAL_SOURCE_ONLY","alerts":[{**a.model_dump(mode="json"),
        "revision_key":a.id+"@"+a.published_at.isoformat(),
        "freshness":("STALE" if (datetime.now(timezone.utc)-a.subscription_as_of).total_seconds()>3600*24 else "RECENT") if a.category=="IPO_SUBSCRIPTION" and a.subscription_as_of else "NOT_APPLICABLE",
        "subscription_total_x":str(a.subscription_total_x) if a.subscription_total_x is not None else None}
        for a in alerts],"total":len(alerts),"live_feed_connected":False,
        "notice":"Local, attributed alerts only. IPO dates and subscription rates are not independently verified or automatically refreshed."}
