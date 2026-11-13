"""Broker research ingestion readiness: no network, scraping or claims of access."""
from datetime import date
from hashlib import sha256
from pydantic import BaseModel,Field,model_validator
from .broker_research import SOURCES

class SourceManifest(BaseModel):
    source:str
    acquisition_mode:str=Field(pattern=r"^(USER_SUBMITTED|LICENSED_API|PUBLIC_PERMISSIONED_FEED)$")
    access_authorized:bool=False
    redistribution_authorized:bool=False
    document_id:str=Field(min_length=1,max_length=120)
    retrieved_on:date
    published_on:date
    report_url:str=Field(min_length=12,max_length=1000)
    content_sha256:str=Field(pattern=r"^[0-9a-f]{64}$")
    analyst:str|None=Field(default=None,max_length=120)

    @model_validator(mode="after")
    def valid(self):
        if self.source not in SOURCES:raise ValueError("Unsupported research provider")
        if self.published_on>self.retrieved_on or self.retrieved_on>date.today():
            raise ValueError("Invalid publication/retrieval chronology")
        if not self.report_url.startswith("https://"):
            raise ValueError("HTTPS report provenance required")
        return self

class IngestionReview(BaseModel):
    manifests:list[SourceManifest]=Field(min_length=1,max_length=100)

def audit_manifests(request:IngestionReview):
    seen=set()
    entries=[]
    for m in request.manifests:
        blockers=[]
        identity=(m.source,m.document_id)
        if identity in seen:blockers.append("DUPLICATE_DOCUMENT_ID")
        seen.add(identity)
        if not m.access_authorized:blockers.append("ACCESS_RIGHTS_NOT_CONFIRMED")
        if m.acquisition_mode!="USER_SUBMITTED":
            blockers.append("AUTOMATED_SOURCE_CONNECTOR_NOT_VERIFIED")
        if not m.redistribution_authorized:blockers.append("NO_REDISTRIBUTION_PERMISSION")
        blockers.extend(["DOCUMENT_CONTENT_NOT_INDEPENDENTLY_VERIFIED",
            "REPORT_CLAIMS_NOT_EXTRACTED_OR_CITED"])
        entries.append({"source":m.source,"document_id":m.document_id,
            "published_on":m.published_on.isoformat(),"retrieved_on":m.retrieved_on.isoformat(),
            "content_sha256":m.content_sha256,"blockers":sorted(set(blockers)),
            "status":"QUARANTINE_REQUIRED"})
    return {"status":"MANIFEST_REVIEW_ONLY","documents_reviewed":len(entries),
        "entries":entries,"automatic_collection_enabled":False,
        "database_writes":0,
        "notice":"Manifest metadata is user-supplied and unauthenticated. No URL was fetched, report stored, parsed or validated; hashes were not independently computed."}
