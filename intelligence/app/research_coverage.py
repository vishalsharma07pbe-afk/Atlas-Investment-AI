"""Transparent source coverage and research-quality checks; no implied broker connectivity."""
from datetime import date
from collections import defaultdict
from pydantic import BaseModel,Field,model_validator
from .broker_research import ResearchRecord,SOURCES

class CoverageRequest(BaseModel):
    instrument_id:str=Field(min_length=3,max_length=80)
    as_of:date=Field(default_factory=date.today)
    max_age_days:int=Field(default=180,ge=1,le=1095)
    records:list[ResearchRecord]=Field(max_length=300)

    @model_validator(mode="after")
    def validate(self):
        if self.as_of>date.today():raise ValueError("Future evaluation date")
        if any(r.instrument_id!=self.instrument_id or r.published_on>self.as_of for r in self.records):
            raise ValueError("Mixed instruments or future research")
        return self

def coverage(request:CoverageRequest):
    by_source=defaultdict(list)
    for r in request.records:by_source[r.source].append(r)
    providers=[]
    for code,name in SOURCES.items():
        reports=by_source[code]
        recent=[r for r in reports if (request.as_of-r.published_on).days<=request.max_age_days]
        dated=sorted(reports,key=lambda r:r.published_on,reverse=True)
        providers.append({"source":code,"name":name,
            "coverage":"FRESH_USER_SUBMITTED" if recent else "STALE_USER_SUBMITTED" if reports else "NO_REPORTS_SUPPLIED",
            "reports_supplied":len(reports),"fresh_reports":len(recent),
            "latest_report_date":dated[0].published_on.isoformat() if dated else None,
            "connected_feed":False})
    fresh_sources=sum(p["fresh_reports"]>0 for p in providers)
    return {"status":"SOURCE_COVERAGE_REVIEW","instrument_id":request.instrument_id,
        "as_of":request.as_of.isoformat(),"fresh_provider_count":fresh_sources,
        "total_supported_source_labels":len(SOURCES),
        "providers":providers,
        "warnings":["NO_LIVE_BROKER_RESEARCH_FEEDS","SOURCE_AUTHENTICITY_UNVERIFIED",
                    "NO_INDEPENDENT_REPORT_CONTENT_VALIDATION"],
        "notice":"Coverage reflects only user-submitted report metadata, not whether a broker actually publishes a report. Missing source is not a negative recommendation."}
