"""Single, fail-closed research pipeline from supplied AMFI snapshot to portfolio valuation.

The source is not independently verified. No NAVs or portfolio values are persisted.
"""
from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field,model_validator
from .amfi_nav_import import parse_amfi
from .nav_refresh_preflight import NavRefreshRecord,NavRefreshPreflightRequest,preflight_nav_refresh
from .mutual_fund_reconciliation import FundPosition,FundNav,FundReconciliationRequest,reconcile_funds

class SnapshotPortfolioRequest(BaseModel):
    text:str=Field(min_length=1,max_length=2_000_000)
    source_name:str=Field(min_length=1,max_length=120)
    source_authorized:bool=False
    positions:list[FundPosition]=Field(min_length=1,max_length=500)
    @model_validator(mode="after")
    def validate_positions(self):
        if len({p.holding_id for p in self.positions})!=len(self.positions):
            raise ValueError("Duplicate holding IDs")
        if any(not p.scheme_code.isascii() for p in self.positions):
            raise ValueError("Scheme codes must use ASCII digits")
        return self

def inspect_snapshot_portfolio(request:SnapshotPortfolioRequest,today:date|None=None)->dict:
    today=today or date.today()
    codes=sorted({p.scheme_code for p in request.positions})
    # One selected code may appear in multiple holdings; it must only appear once in snapshot.
    if len(codes)>200:raise ValueError("Snapshot supports at most 200 distinct schemes")
    snapshot=parse_amfi(request.text,codes,today=today)
    accepted=snapshot["schemes"]
    preflight=preflight_nav_refresh(NavRefreshPreflightRequest(
        source_name=request.source_name,source_authorized=request.source_authorized,
        expected_scheme_codes=codes,
        records=[NavRefreshRecord(scheme_code=s["scheme_code"],nav=Decimal(str(s["nav"])),as_of=date.fromisoformat(s["as_of"])) for s in accepted],
    ),today=today) if accepted else {
        "status":"BLOCKED","blockers":["NO_VALID_NAV_RECORDS","MISSING_EXPECTED_SCHEMES"],
        "stored":False,"refresh_executed":False
    }
    # Missing schemes are allowed in reconciliation to expose row-level diagnostics.
    # The existing reconciliation model requires at least one NAV; skip if none passed.
    reconciliation=reconcile_funds(FundReconciliationRequest(
        positions=request.positions,
        navs=[FundNav(scheme_code=s["scheme_code"],nav=Decimal(str(s["nav"])),
                      as_of=date.fromisoformat(s["as_of"]),source_name=request.source_name)
              for s in accepted]
    ),today=today) if accepted else None
    blockers=list(preflight["blockers"])
    if snapshot["rejected_rows"] and "REJECTED_SNAPSHOT_ROWS" not in blockers:
        blockers.append("REJECTED_SNAPSHOT_ROWS")
    if reconciliation is None or not reconciliation["portfolio_estimate_complete"]:
        if "INCOMPLETE_RECONCILIATION" not in blockers:blockers.append("INCOMPLETE_RECONCILIATION")
    return {
        "status":"READY_FOR_MANUAL_REVIEW" if not blockers else "BLOCKED",
        "blockers":blockers,"snapshot":snapshot,"preflight":preflight,
        "reconciliation":reconciliation,
        "source":{"name":request.source_name,"authorization_user_attested":request.source_authorized,
                  "verification":"USER_SUPPLIED_UNVERIFIED"},
        "stored":False,"refresh_executed":False,"portfolio_updated":False,
        "notice":"Research-only, user-supplied snapshot. A review-ready result is not independently verified or authorization to update holdings."
    }
