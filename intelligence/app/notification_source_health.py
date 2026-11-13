"""Read-only, bounded health view for locally configured IPO notification sources."""
import os
from datetime import datetime,timezone
from pathlib import Path
from pydantic import BaseModel,Field,model_validator
from .notification_feed_sync import Registry
from .notifications import _load

class SourceHealth(BaseModel):
    source_name:str
    enabled:bool
    permission_declared:bool
    alert_count:int
    latest_publication_at:str|None
    latest_subscription_as_of:str|None
    subscription_snapshot_stale:bool|None
    status:str

def inspect_sources(registry_path:Path|None=None):
    path=registry_path or Path(os.getenv("ATLAS_ALERT_FEED_REGISTRY","/app/data/feeds.json"))
    if not path.is_file():
        return {"status":"NOT_CONFIGURED","sources":[],"configured_sources":0,
            "live_feed_connected":False,"notice":"No permissioned IPO source registry configured."}
    if path.stat().st_size>128*1024:raise ValueError("Source registry exceeds size limit")
    registry=Registry.model_validate_json(path.read_bytes())
    alerts=_load()
    now=datetime.now(timezone.utc)
    sources=[]
    for source in registry.feeds:
        matching=[a for a in alerts if a.source_name==source.source_name and a.source_url==source.source_url]
        latest=max((a.published_at for a in matching),default=None)
        subscription=max((a.subscription_as_of for a in matching if a.category=="IPO_SUBSCRIPTION" and a.subscription_as_of),default=None)
        stale=((now-subscription).total_seconds()>86400) if subscription else None
        rights=source.collection_authorized and source.redistribution_authorized
        status=("DISABLED" if not source.enabled else "PERMISSION_NOT_DECLARED" if not rights else
                "NO_ALERTS_IMPORTED" if not matching else "SUBSCRIPTION_STALE" if stale else "LOCAL_DATA_AVAILABLE")
        sources.append(SourceHealth(source_name=source.source_name,enabled=source.enabled,
            permission_declared=rights,alert_count=len(matching),
            latest_publication_at=latest.isoformat() if latest else None,
            latest_subscription_as_of=subscription.isoformat() if subscription else None,
            subscription_snapshot_stale=stale,status=status).model_dump())
    return {"status":"LOCAL_SOURCE_HEALTH","sources":sources,
        "configured_sources":len(sources),"live_feed_connected":False,
        "notice":"This checks only locally supplied data and operator-declared permissions. It does not verify exchange feeds or source licensing."}
