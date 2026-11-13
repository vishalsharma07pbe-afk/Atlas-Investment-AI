"""Source-attributed news event evidence. No news scraping or model-made sentiment."""
from datetime import datetime,timezone,timedelta
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class NewsEvent(BaseModel):
    headline: str = Field(min_length=8,max_length=300)
    source_name: str = Field(min_length=3,max_length=120)
    source_url: str = Field(min_length=8,max_length=600)
    published_at: datetime
    symbol: str | None = Field(default=None,max_length=50,pattern=r"^[A-Za-z0-9._&-]+$")
    geography: Literal["INDIA","GLOBAL","US","EUROPE","ASIA_OTHER","OTHER"]
    event_type: Literal["EARNINGS","REGULATORY","MACRO","MERGER","MANAGEMENT","PRODUCT","MARKET_STRUCTURE","OTHER"]
    sentiment: Literal["POSITIVE","NEGATIVE","MIXED","NEUTRAL","UNKNOWN"] = "UNKNOWN"
    sentiment_method: Literal["USER_LABELLED"] = "USER_LABELLED"

    @model_validator(mode="after")
    def validate_publication(self):
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("Published timestamp must include a timezone")
        if self.published_at > datetime.now(timezone.utc):
            raise ValueError("Future publication timestamps are not allowed")
        if not self.source_url.startswith(("https://","http://")):
            raise ValueError("Source URL must be HTTP(S)")
        return self

class NewsRequest(BaseModel):
    events: list[NewsEvent] = Field(min_length=1,max_length=100)
    max_age_hours: int = Field(default=72,ge=1,le=720)

def analyze_news(events,max_age_hours=72,now=None):
    now=now or datetime.now(timezone.utc)
    seen=set()
    rows=[]
    for event in events:
        key=(event.source_url.strip().lower(),event.published_at.isoformat())
        if key in seen:
            raise ValueError("Duplicate source URL and publication time")
        seen.add(key)
        age=(now-event.published_at).total_seconds()/3600
        rows.append({
            "headline":event.headline,"source_name":event.source_name,
            "source_url":event.source_url,"published_at":event.published_at.isoformat(),
            "symbol":event.symbol,"geography":event.geography,"event_type":event.event_type,
            "sentiment":event.sentiment,"sentiment_method":event.sentiment_method,
            "age_hours":round(age,2),
            "freshness":"FRESH" if 0<=age<=max_age_hours else "STALE",
            "independently_verified":False,
        })
    rows.sort(key=lambda r:r["published_at"],reverse=True)
    return {
        "status":"USER_SUPPLIED_NEWS_EVIDENCE",
        "event_count":len(rows),
        "fresh_count":sum(r["freshness"]=="FRESH" for r in rows),
        "events":rows,
        "notice":"User-labelled news evidence only. No automatic news feed, fact-checking, NLP sentiment, market-impact prediction or trade recommendation.",
    }
