"""Persisted, read-only research snapshots built from existing validated engines.

Public market/fund observations only: never store owner holdings, tokens, or AI prompts.
A failed section does not replace its last good snapshot or masquerade as fresh data.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import os
import re
from pathlib import Path
import sqlite3
from urllib.parse import urlencode

from .market_client import backend_json
from . import steady_momentum, amfi_equity_caps, company_reports, nse_surveillance, nse_pledge_filings, nse_financial_filings, sector_price_context, sector_benchmarks, score_calibration, fip_research, bracket_research
from .screener import screen
from .corporate_action_normalization import archived_crossings
from .replay_evidence import exact_isin
from . import discovery_scan, research_display_archive
from .mutual_fund_recommendations import CATEGORIES, dashboard
from . import official_amfi_ter, forward_earnings, official_amc_factsheet, official_tri, fund_ai_review, unified_decision, stock_qualification, market_regime, release_reconciliation, economic_calendar, global_releases, global_context, global_markets, global_macro, global_fx, automatic_deals, fund_portfolios, fund_disclosures, fund_prospective, research_jobs, research_calendar, daily_briefing, automatic_ai_review, watch_outcomes, automatic_company_evidence, automatic_institutional, automatic_news, portfolio_thesis, automatic_strategy_validation, research_reliability

SECTIONS = ("NSE", "BSE", *CATEGORIES)
DEFAULT_INTERVAL = 900


def config():
    enabled = os.getenv("ATLAS_AUTONOMOUS_RESEARCH_ENABLED", "false").lower() == "true"
    try:
        interval = int(os.getenv("ATLAS_AUTONOMOUS_RESEARCH_INTERVAL_SECONDS", str(DEFAULT_INTERVAL)))
        if not 300 <= interval <= 86400:
            raise ValueError()
    except ValueError:
        return False, DEFAULT_INTERVAL
    return enabled, interval


def now():
    return datetime.now(timezone.utc)


def _connect():
    path = Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB", "/app/ingestion-data/research_snapshots.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS research_sections(
        section TEXT PRIMARY KEY, generated_at TEXT, attempted_at TEXT NOT NULL,
        status TEXT NOT NULL, payload TEXT, error_code TEXT)""")
    return db


def _save(section, result=None):
    instant=now()
    stamp=instant.isoformat()
    with closing(_connect()) as db, db:
        # Seed a legacy last-successful payload even when the first post-upgrade
        # refresh fails. A historical capture always retains its original date.
        if research_display_archive.permitted():
            old=db.execute("SELECT generated_at,payload FROM research_sections WHERE section=?",(section,)).fetchone()
            if old and old["generated_at"] and old["payload"]:
                try:
                    original=datetime.fromisoformat(old["generated_at"])
                    previous=json.loads(old["payload"])
                    if original.tzinfo is not None and original<=instant:
                        research_display_archive.capture(db,section,previous,original,
                            _published_evidence_current(section,previous,original.astimezone(ZoneInfo("Asia/Kolkata")).date()))
                except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
                    pass
            if result is not None:
                try:
                    research_display_archive.capture(db,section,result,instant,
                        _published_evidence_current(section,result,instant.astimezone(ZoneInfo("Asia/Kolkata")).date()))
                except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
                    pass
        if result is None:
            db.execute("""INSERT INTO research_sections(section,attempted_at,status,error_code)
                VALUES(?,?,'FAILED','RESEARCH_REFRESH_FAILED')
                ON CONFLICT(section) DO UPDATE SET attempted_at=excluded.attempted_at,
                status=excluded.status,error_code=excluded.error_code""", (section, stamp))
        else:
            db.execute("""INSERT INTO research_sections VALUES(?,?,?,'READY',?,NULL)
                ON CONFLICT(section) DO UPDATE SET generated_at=excluded.generated_at,
                attempted_at=excluded.attempted_at,status=excluded.status,
                payload=excluded.payload,error_code=NULL""",
                (section, stamp, stamp, json.dumps(result, default=str, allow_nan=False)))


def market_snapshot(exchange):
    if os.getenv("ATLAS_BROAD_DISCOVERY_ENABLED","false").lower()=="true":
        # One local calendar read for the whole sweep; failed calendar
        # affects FIP evidence only, not the established discovery workflow.
        try:calendar=backend_json(f"/api/v1/market-data/strategy-calendar?exchange={exchange}")
        except Exception:calendar=None
        dates=fip_research.calendar_suffix(calendar,exchange,now().astimezone(ZoneInfo("Asia/Kolkata")).date())
        return discovery_scan.scan(exchange,backend_json,lambda e,rows,cutoff:_market_page(e,rows,cutoff,fip_dates=dates),now)
    instruments = backend_json("/api/v1/market-data/discovery-universe?" + urlencode({"exchange": exchange}))
    dates=()
    if isinstance(instruments,list) and any(isinstance(r,dict) and r.get("expected_session") and exact_isin(r.get("isin")) for r in instruments):
        try:calendar=backend_json(f"/api/v1/market-data/strategy-calendar?exchange={exchange}")
        except Exception:calendar=None
        dates=fip_research.calendar_suffix(calendar,exchange,now().astimezone(ZoneInfo("Asia/Kolkata")).date())
    return _market_page(exchange,instruments,fip_dates=dates)


def _market_page(exchange,instruments,cutoff=None,*,fip_dates=()):
    if not isinstance(instruments, list) or len(instruments)>200:
        raise ValueError("INVALID_REGISTRY")
    if any(not isinstance(row,dict) or row.get("exchange")!=exchange or row.get("active") is not True
           or row.get("listing_status")!="ACTIVE" or row.get("series")!="EQ"
           or row.get("instrument_type") not in ("EQUITY","EQ","STOCK")
           or type(row.get("id")) is not int or row["id"]<=0 for row in instruments):
        raise ValueError("INVALID_DISCOVERY_IDENTITY")
    ids=[row["id"] for row in instruments]
    if len(set(ids))!=len(ids):
        raise ValueError("DUPLICATE_DISCOVERY_IDENTITY")
    counts={row.get("recent_registry_count") for row in instruments}
    recent_count=next(iter(counts)) if len(counts)==1 else 0
    if instruments and (type(recent_count) is not int or recent_count<len(instruments)):
        raise ValueError("INVALID_DISCOVERY_COVERAGE")
    today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
    sessions={row.get("expected_session") for row in instruments}
    if len(sessions)>1:
        raise ValueError("INCONSISTENT_DISCOVERY_CALENDAR")
    expected=next(iter(sessions),None)
    expected_session=date.fromisoformat(expected) if expected is not None else None
    if expected_session is not None and not 1<=(today-expected_session).days<=14:
        raise ValueError("INVALID_DISCOVERY_CALENDAR")
    matching_counts={row.get("expected_session_count") for row in instruments}
    matching=next(iter(matching_counts)) if len(matching_counts)==1 else None
    if expected_session is not None and (type(matching) is not int or not 0<=matching<=recent_count):
        raise ValueError("INVALID_SESSION_COVERAGE")
    histories={identifier:[] for identifier in ids}
    history_limit=253 if cutoff is not None else 250
    # At most ten local batch requests per page; no provider requests.
    for offset in range(0,len(ids),20):
        batch=ids[offset:offset+20]
        params={"exchange":exchange,"ids":batch}
        if cutoff is not None:params["cutoff"]=cutoff
        rows=backend_json("/api/v1/market-data/discovery-candles?"+urlencode(params,doseq=True))
        if not isinstance(rows,list) or len(rows)>len(batch)*history_limit:
            raise ValueError("INVALID_DISCOVERY_HISTORY")
        for row in rows:
            if not isinstance(row,dict) or type(row.get("instrument_id")) is not int or row["instrument_id"] not in batch:
                raise ValueError("DISCOVERY_HISTORY_IDENTITY_MISMATCH")
            if str(row["trade_date"])<today.isoformat():
                histories[row["instrument_id"]].append(row)
        if any(len(histories[i])>history_limit for i in batch):
            raise ValueError("DISCOVERY_HISTORY_LIMIT_EXCEEDED")
    instant=now()
    action_events=automatic_company_evidence.cached_action_events(_connect,[r.get("isin") for r in instruments],instant)
    result = screen(instruments, lambda identifier:{"candles":histories[identifier]}, as_of=today,
                    universe_limit=200, max_age_days=4, include_horizons=True, batch_loaded=True, expected_session=expected_session,
                    action_events=action_events,instant=instant,fip_dates=fip_dates)
    result["discovery_coverage"]={"recent_registry_count":recent_count,"selected_count":len(ids),
        "selection_limit":200,"selection_method":"EXPECTED_SESSION_THEN_DAILY_TRADED_VALUE",
        "expected_session_count":matching if expected_session else None,
        "history_batch_size":20,"history_limit":history_limit,"annual_depth_count":result.get("annual_depth_count",0),"calendar_status":"PUBLISHED_SESSION" if expected_session else "CALENDAR_UNVERIFIED",
        "expected_session":expected,"calendar_checked_on":today.isoformat()}
    # Attach registry identity, not ticker-based guesses, for company evidence.
    registry = {row["id"]: row for row in instruments if row.get("active") is True
                and row.get("listing_status") == "ACTIVE" and row.get("series") == "EQ"}
    for group in result["horizons"].values():
        for candidate in group["candidates"]:
            record = registry.get(candidate["id"])
            if record and record.get("symbol") == candidate["symbol"] and record.get("exchange") == candidate["exchange"]:
                candidate["isin"] = record.get("isin")
    result["notice"] = ("Automatically refreshed daily observations from up to 200 recent active cash equities per exchange, prioritizing the expected completed session, then latest daily traded value. "
                        "Not live intraday signals, full-exchange rankings, or recommendations.")
    return result


FUND_GATES=frozenset(("OFFICIAL_CATEGORY","EXACT_DIRECT_GROWTH_PLAN",
    "CATEGORY_SPECIFIC_RISK_MODEL_REQUIRED","CATEGORY_STRATEGY_MISMATCH","FRESH_DATED_NAV",
    "OFFICIAL_RISKOMETER","THREE_YEAR_NAV_HISTORY","EXPENSE_RATIO","UNDERLYING_INDEX",
    "TRACKING_DIFFERENCE","TRACKING_ERROR","ONE_YEAR_RETURN","THREE_YEAR_RETURN",
    "PEER_PERCENTILE","BENCHMARK_HIT_RATE","WORST_ROLLING_RETURN","MAX_DRAWDOWN",
    "VOLATILITY","RECENT_PORTFOLIO_DISCLOSURE","PORTFOLIO_COVERAGE_80_PERCENT",
    "INDEX_OUTLOOK_COVERAGE_70_PERCENT","EARNINGS_COVERAGE_70_PERCENT",
    "VALUATION_COVERAGE_60_PERCENT","FORWARD_EARNINGS_GROWTH","VALUATION_EVIDENCE",
    "SECTOR_DRIVERS","CONCENTRATION","LIQUIDITY","DUPLICATE_SCHEME_IDENTITY",
    "SELECTED_HORIZON_OR_RISK_REVIEW_REQUIRED"))

def _fund_qualification_counts(summary):
    """Project bounded counts, never individual exclusions or unknown labels."""
    if not isinstance(summary,dict):
        return None
    keys=("evaluated_count","top_eligible_count","growth_eligible_count")
    if any(type(summary.get(k)) is not int or not 0<=summary[k]<=40 for k in keys):
        return None
    evaluated,top,growth=(summary[k] for k in keys)
    excluded=summary.get("excluded")
    if max(top,growth)>evaluated or not isinstance(excluded,list) or len(excluded)>evaluated:
        return None
    seen=set()
    counts=[{},{}]
    withheld=[0,0]
    for row in excluded:
        if not isinstance(row,dict) or not isinstance(row.get("identifier"),str) or not row["identifier"] or row["identifier"] in seen:
            return None
        seen.add(row["identifier"])
        for i,key in enumerate(("top_performer_missing","growth_outlook_missing")):
            values=row.get(key)
            if not isinstance(values,list) or any(not isinstance(v,str) for v in values):
                return None
            if values:
                withheld[i]+=1
            for gate in {v if v in FUND_GATES else "UNKNOWN_GATE" for v in values}:
                counts[i][gate]=counts[i].get(gate,0)+1
        if not row["top_performer_missing"] and not row["growth_outlook_missing"]:
            return None
    if withheld!=[evaluated-top,evaluated-growth]:
        return None
    return {**{k:summary[k] for k in keys},"top_missing_gate_counts":counts[0],
            "growth_missing_gate_counts":counts[1]}


def fund_snapshot(category):
    # Public category discovery is not a personalized recommendation. Keep
    # the existing suitability filters authoritative for the qualified lists.
    result = dashboard(category, 60, "MODERATE",category_only=True)
    # Keep strict rankings and compact counts, not the individual exclusions.
    snapshot={key: result[key] for key in (
        "category", "coverage", "top_performers", "growth_outlook",
        "recommendation_status", "blockers", "notice", "filters", "historical_coverage")}
    snapshot["qualification_counts"]=_fund_qualification_counts(result.get("qualification_summary"))
    drivers=result.get("growth_driver_review") or {}
    if drivers.get("methodology")=="MF-QUARTERLY-DRIVERS-1":
        snapshot["growth_driver_review"]={"methodology":drivers["methodology"],"status":drivers.get("status"),
            "items":[{k:row.get(k) for k in ("identifier","name","portfolio_date","quarter","nav_date","joint_coverage_weight_percent",
                "joint_growth_weight_percent","review_weight_percent","state","qualified","forecast_return_percent")}
                for row in drivers.get("items",[])[:5] if isinstance(row,dict) and row.get("qualified") is False]}
        # Persist only validated public numerical scenarios, never arbitrary
        # nested publisher/model fields from the full fund research response.
        from .investment_analyst import fund_growth
        today=now().astimezone(ZoneInfo("Asia/Kolkata")).date()
        for compact,original in zip(snapshot["growth_driver_review"]["items"],
                (row for row in drivers.get("items",[])[:5] if isinstance(row,dict) and row.get("qualified") is False)):
            growth=fund_growth(original,today)
            if growth:
                compact["experimental_forward"]={
                    "status":"UNCALIBRATED_PERSISTENCE_EXPERIMENT","qualified":False,
                    "observed_quarter":growth["observed_quarter"],"target_quarter":growth["target_quarter"],
                    "covered_weight_percent":growth["coverage_percent"],
                    "positive_joint_growth_weight_percent":original["experimental_forward"]["positive_joint_growth_weight_percent"],
                    "covered_subset_revenue_persistence_percent":growth["revenue_yoy_percent"],
                    "covered_subset_profit_persistence_percent":growth["profit_yoy_percent"]}
    # Compact exact public composition targets for the existing underlying
    # research scheduler. No raw holdings, names or source URLs are persisted.
    targets=[]
    for row in (result.get("portfolio_evidence") or {}).get("items",[])[:5]:
        if not isinstance(row,dict) or row.get("status")!="SECONDARY_COMPOSITION_ONLY" or row.get("source")!="TIGZIG_AMC_DERIVED":continue
        fund=row.get("fund_id");code=row.get("scheme_code")
        try:
            day=date.fromisoformat(row["portfolio_date"])
            if not isinstance(fund,str) or not re.fullmatch(r"[A-Za-z0-9:_.-]{1,80}",fund) or not isinstance(code,str) or not re.fullmatch(r"[1-9][0-9]{0,8}",code):continue
            targets.append({"fund_id":fund,"scheme_code":code,"portfolio_date":day.isoformat()})
        except (ValueError,TypeError,KeyError):continue
    if targets:snapshot["portfolio_research_targets"]=targets
    # Only aggregate public source coverage. Never persist source URLs or holdings.
    for key,fields in (("official_tri_coverage",("configured_count","available_count","local_csv_count")),("official_amc_coverage",("matched_schemes",)),("automatic_amfi_ter_coverage",("matched_schemes",))):
        block=result.get(key)
        if isinstance(block,dict):
            snapshot[key]={k:block[k] for k in fields if type(block.get(k)) is int and 0<=block[k]<=40}
    prospective=result.get("prospective_validation") or {}
    if isinstance(prospective.get("status"),str):
        snapshot["prospective_validation"]={"status":prospective["status"]}
    # Keep only the bounded public shortlist, never the full report or
    # arbitrary secondary source payload. Qualification lists stay separate.
    shortlist=result.get("historical_research_shortlist") or {}
    if shortlist.get("methodology")=="MF-MATCHED-PEER-1" and shortlist.get("category")==category:
        snapshot["historical_research_shortlist"]={k:shortlist.get(k) for k in
            ("methodology","category","status","eligible_count","matched_count","cohort_count","first_date","last_date","date_digest","notice","scope","selected_suitability")}
        snapshot["historical_research_shortlist"]["items"]=[
            {k:r.get(k) for k in ("identifier","name","isin_growth","nav","nav_date","score","weekly_cagr_percent","weekly_drawdown_percent","worst_rolling_year_percent","annualized_volatility_percent","rolling_peer_above_median_percent","relative_risk","status","qualified")}
            for r in shortlist.get("items",[])[:5] if isinstance(r,dict) and r.get("qualified") is False and r.get("status")=="HISTORICAL_RESEARCH_ONLY"]
        from . import research_synthesis
        snapshot["fund_decision_evidence"]=research_synthesis.compact_fund_context(shortlist.get("items",[]),result.get("research_reports",[]),category,now().astimezone(ZoneInfo("Asia/Kolkata")).date())
    return snapshot


def refresh_once(market_loader=market_snapshot, fund_loader=fund_snapshot):
    """Independent bounded sections, with no browser or external AI requirement."""
    for section in SECTIONS:
        try:
            result = market_loader(section) if section in ("NSE", "BSE") else fund_loader(section)
            _save(section, result)
        except Exception:
            # Do not persist provider errors, URLs, credentials or traceback text.
            _save(section)


def _published_evidence_current(section, result, today):
    """Reapply observation-date limits at read time, not just generation time.

    The entire section becomes stale if any published watch fails its original
    date gate. This avoids silently reranking an incomplete persisted sample.
    Empty successful samples remain READY; READY is processing, not coverage.
    """
    def fresh(value, minimum, maximum):
        return minimum <= (today-date.fromisoformat(value)).days <= maximum

    if section in ("NSE", "BSE"):
        coverage=result.get("discovery_coverage") or {}
        expected=coverage.get("expected_session")
        # A published session assertion belongs only to its checked IST date.
        if expected is not None and coverage.get("calendar_checked_on")!=today.isoformat():
            return False
        if expected is not None and not fresh(expected,1,4):
            return False
        def equity_fresh(item):
            return fresh(item["as_of"],1,4) and (expected is None or item["as_of"]==expected)
        for key in ("top_gainers", "top_losers", "momentum_leaders"):
            if any(not equity_fresh(item) for item in result.get(key, [])):
                return False
        for group in result.get("horizons", {}).values():
            if any(not equity_fresh(item) for item in group.get("candidates", [])):
                return False
    else:
        history = result.get("historical_coverage") or {}
        for key in ("items", "risk_adjusted_items"):
            if any(not fresh(item["nav_date"], 0, 7) or item["nav_date"] != history.get("comparison_date")
                   for item in history.get(key, [])):
                return False
        shortlist=result.get("historical_research_shortlist") or {}
        if shortlist.get("items"):
            if shortlist.get("category")!=section or shortlist.get("methodology")!="MF-MATCHED-PEER-1" or shortlist.get("last_date")!=history.get("comparison_date"):
                return False
            if any(not fresh(item["nav_date"],0,7) or item["nav_date"]!=shortlist["last_date"] or item.get("qualified") is not False
                   for item in shortlist["items"]):
                return False
        drivers=result.get("growth_driver_review") or {}
        if any(not fresh(row["portfolio_date"],0,60) or not fresh(row["quarter"],0,150) or not fresh(row["nav_date"],0,7) or row.get("qualified") is not False
               for row in drivers.get("items",[])):
            return False
        # The current strict catalog cannot qualify recommendations without
        # evidence, but recheck dates defensively if qualified picks are stored.
        for key in ("top_performers", "growth_outlook"):
            if any(not fresh(item["fund"]["nav_date"], 0, 7) for item in result.get(key, [])):
                return False
    return True


def _revalidate_reported_actions(sections,current):
    """A newly acquired positive action report invalidates the saved sweep.

    Don't patch a truncated top-k list or stale breadth aggregate in place.
    Keep the original capture for diagnostics; all READY-only consumers wait
    for the existing scheduled scan to rebuild it using the new evidence.
    """
    work=[]
    identities=set()
    for section in sections:
        if section.get("section") not in ("NSE","BSE") or section.get("status")!="READY":continue
        result=section.get("result") or {}
        rows=result.get("company_research_universe")
        if not isinstance(rows,list) or len(rows)>20000:continue
        valid=[]
        for row in rows:
            if not isinstance(row,dict) or row.get("exchange")!=section["section"] or not exact_isin(row.get("isin")):continue
            try:
                last=date.fromisoformat(row["as_of"])
                # Upgrade old snapshots conservatively until the next scan
                # supplies the exact original observation interval.
                first=date.fromisoformat(row["first_date"]) if "first_date" in row else last-timedelta(days=1100)
                if not 0<(last-first).days<=1100:continue
            except (TypeError,ValueError,KeyError,OverflowError):continue
            identities.add(row["isin"])
            valid.append((row["isin"],first,last))
        work.append((section,valid))
    if not identities:return
    events=automatic_company_evidence.cached_action_events(_connect,identities,current)
    for section,rows in work:
        if any(archived_crossings(events.get(isin),first,last) for isin,first,last in rows if isin in events):
            section["status"]="STALE"
            section["error_code"]="NEW_REPORTED_ACTION_RESCAN_REQUIRED"


def _read_sections(section_names,enabled,interval,current):
    # All callers use the identical observation-date and section-state gates.
    # Filter in SQLite before materializing payloads, not after JSON decoding.
    placeholders=",".join("?" for _ in section_names)
    with closing(_connect()) as db:
        records = {row["section"]: row for row in db.execute(
            "SELECT * FROM research_sections WHERE section IN ("+placeholders+")",section_names)}
    sections = []
    today=current.astimezone(ZoneInfo("Asia/Kolkata")).date()
    for section in section_names:
        row = records.get(section)
        if row is None:
            sections.append({"section": section, "status": "PENDING" if enabled else "DISABLED",
                             "generated_at": None, "attempted_at": None, "result": None})
            continue
        error_code = row["error_code"]
        try:
            result = json.loads(row["payload"]) if row["payload"] else None
            if result is not None and not isinstance(result, dict):
                raise ValueError("INVALID_SNAPSHOT")
            age = (current - datetime.fromisoformat(row["generated_at"])).total_seconds() if row["generated_at"] else None
            stale = age is None or age < 0 or age > max(3600, interval * 3)
            status = "DISABLED" if not enabled else "FAILED" if row["status"] == "FAILED" else "STALE" if stale else "READY"
            if status == "READY":
                if result is None:
                    raise ValueError("MISSING_SNAPSHOT")
                if not _published_evidence_current(section, result, today):
                    status = "STALE"
                    error_code = "UNDERLYING_OBSERVATION_STALE"
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            result = None
            status = "FAILED" if enabled else "DISABLED"
            error_code = "INVALID_STORED_RESEARCH_SNAPSHOT"
        if section in CATEGORIES and isinstance(result,dict) and (not fund_portfolios.permitted() or not automatic_company_evidence.permitted()):
            result.pop("growth_driver_review",None)
            result.pop("portfolio_research_targets",None)
        if section in CATEGORIES and isinstance(result,dict):
            if not official_tri.permitted():result.pop("official_tri_coverage",None)
            if not official_amc_factsheet.permitted():result.pop("official_amc_coverage",None)
            # Only retain source-specific context while the respective permissions remain enabled.
            from . import research_synthesis, fund_local_evidence
            records=result.pop("fund_decision_evidence",[])
            kept=[]
            for item in (result.get("historical_research_shortlist") or {}).get("items",[])[:5]:
                if not isinstance(item,dict):continue
                context=research_synthesis.saved_fund_context(item,records,section,today,website=official_amfi_ter.permitted(),local=fund_local_evidence.permitted(),tri=official_tri.permitted(),secondary=fund_disclosures.permitted())
                kept.append({k:item.get(k) for k in ("identifier","isin_growth","nav_date")} | {"category":section,"context":context})
            if kept:result["fund_decision_evidence"]=kept
        sections.append({"section": section, "status": status,
                         "generated_at": row["generated_at"], "attempted_at": row["attempted_at"],
                         "result": result, "error_code": error_code})
    if enabled:
        _revalidate_reported_actions(sections,current)
    return {"enabled": enabled, "interval_seconds": interval, "sections": sections,
            "scope": "PUBLIC_MARKET_RESEARCH_ONLY",
            "research_date":today.isoformat(),
            "notice": "Snapshot time is not the underlying observation time. Missing evidence never becomes a recommendation."}


def read_market_snapshot():
    """Internal lightweight read for equity-only consumers; no fund payloads or enrichment."""
    enabled,interval=config()
    return _read_sections(("NSE","BSE"),enabled,interval,now())


def read_snapshot(include_ai=True):
    enabled,interval=config()
    current=now()
    snapshot=_read_sections(SECTIONS,enabled,interval,current)
    if include_ai:
        try:
            snapshot["strategy_validation"] = automatic_strategy_validation.read(_connect,current,snapshot=snapshot) if enabled else {"status":"DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["strategy_validation"] = {"status":"UNAVAILABLE"}
        try:
            snapshot["institutional_activity"] = automatic_institutional.read(_connect) if enabled else {"status":"AUTOMATION_DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["institutional_activity"] = {"status":"UNAVAILABLE"}
        try:
            snapshot["global_fx"]=global_fx.read(_connect,current) if enabled else {"status":"AUTOMATION_DISABLED","items":[],"notice":global_fx.NOTICE}
        except (ValueError,OSError,sqlite3.Error):
            snapshot["global_fx"]={"status":"UNAVAILABLE","items":[],"notice":global_fx.NOTICE}
        try:
            snapshot["global_macro"]=global_macro.read(_connect,current) if enabled else {"status":"AUTOMATION_DISABLED","sources":[],"notice":global_macro.NOTICE}
        except (ValueError,OSError,sqlite3.Error):
            snapshot["global_macro"]={"status":"UNAVAILABLE","sources":[],"notice":global_macro.NOTICE}
        try:
            snapshot["global_markets"]=global_markets.read(_connect,current) if enabled else {"status":"AUTOMATION_DISABLED","items":[],"notice":global_markets.NOTICE}
        except (ValueError,OSError,sqlite3.Error):
            snapshot["global_markets"]={"status":"UNAVAILABLE","items":[],"notice":global_markets.NOTICE}
        try:
            automatic_deals.attach(snapshot,_connect,current)
        except (ValueError,OSError,sqlite3.Error):
            snapshot["institutional_activity"]["deal_reports"]={"status":"UNAVAILABLE"}
        try:
            automatic_company_evidence.attach(snapshot, _connect,current)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_company_status"] = "UNAVAILABLE"
        try:
            snapshot["research_reliability"] = research_reliability.read(_connect,current) if enabled else {"status":"DISABLED"}
        except (ValueError, OSError, sqlite3.Error):
            snapshot["research_reliability"] = {"status":"UNAVAILABLE"}
        research_reliability.attach(snapshot,snapshot["research_reliability"],current.astimezone(ZoneInfo("Asia/Kolkata")).date())
        try:
            snapshot["global_releases"]=global_releases.read(_connect,current) if enabled else {"status":"AUTOMATION_DISABLED","sources":[],"events":[],"notice":global_releases.NOTICE}
        except (ValueError,OSError,sqlite3.Error):
            snapshot["global_releases"]={"status":"UNAVAILABLE","sources":[],"events":[],"notice":global_releases.NOTICE}
        try:
            snapshot["economic_calendar"]=economic_calendar.read(_connect,current) if enabled else economic_calendar.empty("AUTOMATION_DISABLED")
        except (ValueError,OSError,sqlite3.Error):
            snapshot["economic_calendar"]=economic_calendar.empty("UNAVAILABLE")
        release_reconciliation.attach(snapshot,current)
        global_context.attach(snapshot,current)
        try:
            market_regime.attach(snapshot,_connect,current)
        except (ValueError,OSError,sqlite3.Error):
            snapshot["market_regime"]=market_regime.empty("UNAVAILABLE")
        try:
            nse_surveillance.attach(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["exchange_surveillance"]={"status":"UNAVAILABLE","notice":nse_surveillance.NOTICE}
        try:
            nse_pledge_filings.attach(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["independent_pledge_filings"]={"status":"UNAVAILABLE","notice":nse_pledge_filings.NOTICE}
        try:
            nse_financial_filings.attach(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["independent_financial_filings"]={"status":"UNAVAILABLE","notice":nse_financial_filings.NOTICE}
        try:
            sector_benchmarks.attach(snapshot,_connect,current)
            sector_price_context.attach(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["sector_price_context"]={"status":"UNAVAILABLE","notice":sector_price_context.NOTICE}
        try:
            snapshot["steady_momentum"] = steady_momentum.summarize(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["steady_momentum"]={"status":"AWAITING_EVIDENCE","items":[],"notice":steady_momentum.NOTICE}
        try:
            automatic_news.attach(snapshot,_connect,current)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_news_status"]="UNAVAILABLE"
        try:
            automatic_ai_review.attach(snapshot, _connect)
        except (ValueError, OSError, sqlite3.Error):
            snapshot["automatic_ai_status"] = "UNAVAILABLE"
        try:
            score_calibration.attach(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["score_calibration"]={"status":"UNAVAILABLE","notice":score_calibration.NOTICE}
        try:
            snapshot["bracket_research"]=bracket_research.prospective(_connect,current) if enabled else {"status":"DISABLED"}
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["bracket_research"]={"status":"UNAVAILABLE","notice":bracket_research.NOTICE}
        try:
            if fund_portfolios.permitted() and automatic_company_evidence.permitted():
                fund_ai_review.attach(snapshot,_connect)
            else:
                for section in snapshot.get("sections",[]):
                    (section.get("result") or {}).pop("growth_driver_review",None)
        except (ValueError,TypeError,OSError,sqlite3.Error):
            pass
        research_reliability.attach_conclusions(snapshot)
        stock_qualification.attach(snapshot,current.astimezone(ZoneInfo("Asia/Kolkata")).date(),current)
        snapshot["daily_briefing"] = daily_briefing.summarize(snapshot)
        company_reports.attach(snapshot,current)
        from . import multi_strategy
        try:
            snapshot["multi_strategy"]=multi_strategy.summarize(snapshot,_connect,current)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,sqlite3.Error):
            snapshot["multi_strategy"]={"methodology":multi_strategy.VERSION,"status":"UNAVAILABLE","items":[],"notice":multi_strategy.NOTICE}
        snapshot["multi_strategy"]["historical_validation"]=(snapshot.get("strategy_validation") or {}).get("multi_strategy")
        try:
            from . import multi_strategy_prospective
            snapshot["multi_strategy"]["prospective_validation"]=multi_strategy_prospective.summary(_connect,current)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,sqlite3.Error):
            snapshot["multi_strategy"]["prospective_validation"]={"status":"UNAVAILABLE","lanes":{},"notice":"Paper-tracking evidence unavailable."}
        try:
            snapshot["forward_earnings_validation"]=forward_earnings.summary(_connect,current) if enabled else {"status":"DISABLED"}
        except (ValueError,TypeError,OSError,sqlite3.Error):
            snapshot["forward_earnings_validation"]={"status":"UNAVAILABLE"}
        try:
            snapshot["unified_decision"]=unified_decision.summarize(snapshot,current.astimezone(ZoneInfo("Asia/Kolkata")).date())
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            # An invalid optional decision projection must not break the existing research endpoint.
            snapshot["unified_decision"]={"methodology":unified_decision.VERSION,"status":"UNAVAILABLE","notice":unified_decision.NOTICE}
    return snapshot


def read_overview():
    """UI-only projection, appended after all current qualification consumers."""
    snapshot=read_snapshot()
    snapshot["historical_display"]=research_display_archive.display(_connect,snapshot,now())
    from . import investment_analyst,analyst_committee
    from copy import deepcopy
    instant=now()
    try:
        snapshot["investment_analyst"]=investment_analyst.analyze(snapshot,instant.astimezone(ZoneInfo("Asia/Kolkata")).date(),instant)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        snapshot["investment_analyst"]={"methodology":investment_analyst.VERSION,"status":"UNAVAILABLE","stocks":[],"funds":[],"next_steps":[],"notice":investment_analyst.NOTICE}
    try:
        # Optional model cache corruption or a failed read must not replace
        # the usable deterministic report with an empty research screen.
        with_committee=deepcopy(snapshot["investment_analyst"])
        analyst_committee.attach(with_committee,_connect,instant)
        snapshot["investment_analyst"]=with_committee
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
        snapshot["investment_analyst"]["committee"]={"methodology":analyst_committee.VERSION,
            "status":"UNAVAILABLE","reviewed_providers":0,"notice":analyst_committee.NOTICE}
    from . import analyst_source_discovery
    try:
        analyst_source_discovery.attach(snapshot["investment_analyst"],_connect,instant)
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError):
        snapshot["investment_analyst"]["source_discovery"]={"status":"UNAVAILABLE","links":[],"notice":analyst_source_discovery.NOTICE}
    from . import decision_quality,decision_outcomes
    try:
        snapshot["investment_analyst"]["decision_outcomes"]=decision_outcomes.summary(_connect,instant)
    except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError):
        snapshot["investment_analyst"]["decision_outcomes"]={"status":"UNAVAILABLE","states":{},"notice":decision_outcomes.NOTICE}
    try:
        decision_quality.attach(snapshot["investment_analyst"],instant.astimezone(ZoneInfo("Asia/Kolkata")).date())
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        # Failure of final policy must not leave a positive allocation action.
        report=snapshot["investment_analyst"]
        for row in report.get("stocks",[]):row["action"]="WATCH_FOR_CONFIRMATION"
        for group in report.get("funds",[]):
            for row in group.get("items",[]):row["action"]="WATCH_FOR_CONFIRMATION"
        report["decision_quality"]={"methodology":decision_quality.VERSION,"status":"UNAVAILABLE","qualified":False,"notice":decision_quality.NOTICE}
    return snapshot


def job_status():
    enabled,_=config()
    if not enabled:
        return {"status":"DISABLED","jobs":[]}
    current=now()
    result=research_jobs.status(_connect,research_jobs.definitions(SECTIONS),current.timestamp())
    calendar_job=next(j for j in result["jobs"] if j["job"]=="CALENDAR_CONTEXT")
    result["calendar"]=research_calendar.read(_connect,current) if calendar_job["status"]=="PASS_COMPLETED" else {"status":"CALENDAR_UNAVAILABLE_OR_PENDING","sessions":[]}
    result["company_acquisition"]=automatic_company_evidence.acquisition_status(read_market_snapshot(),_connect,current)
    result["fund_disclosure_acquisition"]=fund_disclosures.ingestion_coverage(current)
    result["global_source_recovery"]=global_macro.quote_recovery.status(current.timestamp(),global_sources=True)
    return result


def _fund_research_targets(current):
    enabled,interval=config()
    # Priority enrichment is optional; a missing snapshot store cannot
    # block the existing authorized broad fund acquisition queue.
    if not enabled:return {}
    try:snapshot=_read_sections(CATEGORIES,enabled,interval,current)
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError):return {}
    today=current.astimezone(ZoneInfo("Asia/Kolkata")).date()
    targets={};conflicts=set()
    for section in snapshot["sections"]:
        if section.get("status")!="READY":continue
        result=section.get("result") or {}
        if result.get("category")!=section["section"]:continue
        for row in result.get("portfolio_research_targets",[])[:5]:
            if not isinstance(row,dict):continue
            fund=row.get("fund_id")
            try:
                if not isinstance(fund,str) or not re.fullmatch(r"[A-Za-z0-9:_.-]{1,80}",fund) or not 0<=(today-date.fromisoformat(row["portfolio_date"])).days<=60:continue
            except (ValueError,TypeError,KeyError):continue
            if fund in targets and targets[fund]!=row["portfolio_date"]:conflicts.add(fund)
            targets[fund]=row["portfolio_date"]
    return {fund:day for fund,day in targets.items() if fund not in conflicts}


def _execute_job(job):
    """Dispatch existing bounded engines, with explicit evidence/config gates."""
    if job=="OFFICIAL_AMFI_TER":
        if not official_amfi_ter.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if official_amfi_ter.refresh(now()) else "WAITING_EVIDENCE"
    if job=="OFFICIAL_AMC_FACTSHEETS":
        if not official_amc_factsheet.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if official_amc_factsheet.refresh(now()) else "WAITING_EVIDENCE"
    if job=="OFFICIAL_TRI_DOWNLOAD":
        if not official_tri.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if official_tri.refresh(now()) else "WAITING_EVIDENCE"
    if job=="FUND_AI_REVIEW":
        if not automatic_ai_review.providers() or not fund_portfolios.permitted() or not automatic_company_evidence.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        enabled,interval=config()
        snapshot=_read_sections(CATEGORIES,enabled,interval,now())
        if not any(fund_ai_review.candidates(snapshot)):
            return "WAITING_EVIDENCE"
        fund_ai_review.refresh(snapshot,_connect)
        return "PASS_COMPLETED"
    if job=="SECTOR_BENCHMARKS":
        if not sector_benchmarks.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if sector_benchmarks.refresh(_connect,now()) else "WAITING_EVIDENCE"
    if job=="NSE_FINANCIAL_FILINGS":
        if not nse_financial_filings.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if nse_financial_filings.refresh(read_market_snapshot(),_connect,now()) else "WAITING_EVIDENCE"
    if job=="NSE_PLEDGE_FILINGS":
        if not nse_pledge_filings.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if nse_pledge_filings.refresh(read_market_snapshot(),_connect,now()) else "WAITING_EVIDENCE"
    if job=="NSE_SURVEILLANCE":
        if not nse_surveillance.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if nse_surveillance.refresh(_connect,now()) else "WAITING_EVIDENCE"
    if job=="AMFI_EQUITY_CAP":
        if not amfi_equity_caps.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        today=now().astimezone(ZoneInfo("Asia/Kolkata")).date()
        updated=amfi_equity_caps.refresh(_connect,today)
        published=amfi_equity_caps.publish_to_scheduler(_connect,today)
        return "PASS_COMPLETED" if updated and published else "WAITING_EVIDENCE"
    if job=="PUBLIC_RESEARCH_ALERTS":
        from . import public_alert_history
        snapshot=read_market_snapshot()
        if not snapshot["enabled"]:
            return "DISABLED_OR_NOT_AUTHORIZED"
        public_alert_history.refresh(_connect,snapshot,now())
        return "PASS_COMPLETED"
    if job=="MARKET_REGIME":
        return "PASS_COMPLETED" if market_regime.refresh(_connect) else "WAITING_EVIDENCE"
    if job=="ECONOMIC_CALENDAR":
        if not economic_calendar.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        economic_calendar.refresh(_connect)
        return "PASS_COMPLETED"
    if job in global_releases.JOBS:
        source=global_releases.JOBS[job]
        if not global_releases.permitted(source):
            return "DISABLED_OR_NOT_AUTHORIZED"
        global_releases.refresh(_connect,source)
        return "PASS_COMPLETED"
    if job in global_markets.JOBS:
        series=global_markets.JOBS[job]
        if not global_markets.permitted(series):
            return "DISABLED_OR_NOT_AUTHORIZED"
        global_markets.refresh(_connect,series)
        return "PASS_COMPLETED"
    if job in global_macro.JOBS:
        source=global_macro.JOBS[job]
        if not global_macro.permitted(source):
            return "DISABLED_OR_NOT_AUTHORIZED"
        global_macro.refresh(_connect,source)
        return "PASS_COMPLETED"
    if job=="GLOBAL_FX":
        if not global_fx.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        global_fx.refresh(_connect)
        return "PASS_COMPLETED"
    if job=="DEAL_REPORTS":
        if not automatic_deals.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if automatic_deals.refresh(_connect) else "WAITING_EVIDENCE"
    if job=="FORWARD_EARNINGS_BASELINE":
        if not automatic_company_evidence.permitted():return "DISABLED_OR_NOT_AUTHORIZED"
        enabled,interval=config()
        if not enabled:return "DISABLED_OR_NOT_AUTHORIZED"
        current=now()
        forward_earnings.refresh(_read_sections(("NSE","BSE"),enabled,interval,current),_connect,current)
        return "PASS_COMPLETED"
    if job=="FUND_WATCH_OUTCOMES":
        enabled,interval=config()
        if not enabled:return "DISABLED_OR_NOT_AUTHORIZED"
        current=now()
        fund_prospective.refresh(_read_sections(CATEGORIES,enabled,interval,current),current)
        return "PASS_COMPLETED"
    if job=="FUND_COMPANY_EVIDENCE":
        if not fund_portfolios.permitted() or not automatic_company_evidence.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        current=now()
        ids=fund_portfolios.research_identities(current,preferred_funds=_fund_research_targets(current))
        if not ids:
            return "WAITING_EVIDENCE"
        outcome=automatic_company_evidence.refresh({"enabled":True,"sections":[]},_connect,explicit_isins=ids)
        return "PASS_COMPLETED" if outcome in ("AVAILABLE","PARTIAL") else "WAITING_EVIDENCE"
    if job=="FUND_PORTFOLIOS":
        if not fund_portfolios.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if fund_portfolios.refresh()>0 else "WAITING_EVIDENCE"
    if job=="FUND_DISCLOSURES":
        if not fund_disclosures.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        return "PASS_COMPLETED" if fund_disclosures.refresh()>0 else "WAITING_EVIDENCE"
    if job=="CALENDAR_CONTEXT":
        research_calendar.refresh(_connect)
        return "PASS_COMPLETED"
    if job.startswith("SECTION:"):
        section=job.split(":",1)[1]
        if section not in SECTIONS:
            raise ValueError("INVALID_RESEARCH_SECTION")
        try:
            result=market_snapshot(section) if section in ("NSE","BSE") else fund_snapshot(section)
            _save(section,result)
        except Exception:
            _save(section)
            raise
        return "PASS_COMPLETED"
    if job=="PORTFOLIO_REVIEW":
        if not portfolio_thesis.enabled():
            return "DISABLED_OR_NOT_AUTHORIZED"
        portfolio_thesis.refresh()
        return "PASS_COMPLETED"
    if job=="INSTITUTIONAL_FLOWS":
        if not automatic_institutional.permitted():
            return "DISABLED_OR_NOT_AUTHORIZED"
        automatic_institutional.refresh(_connect,calendar_loader=backend_json)
        return "PASS_COMPLETED"
    if job=="COMPANY_EVIDENCE" and not automatic_company_evidence.permitted():
        return "DISABLED_OR_NOT_AUTHORIZED"
    if job=="COMPANY_NEWS" and not automatic_news.permitted():
        return "DISABLED_OR_NOT_AUTHORIZED"
    if job=="MULTI_STRATEGY_PUBLICATION":
        from . import multi_strategy_prospective
        instant=now()
        snapshot=read_snapshot()
        if not snapshot.get("enabled"):return "DISABLED_OR_NOT_AUTHORIZED"
        multi_strategy_prospective.publish(snapshot,_connect,instant)
        from . import investment_analyst,analyst_committee,decision_quality,decision_outcomes
        today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
        report=investment_analyst.analyze(snapshot,today,instant)
        analyst_committee.attach(report,_connect,instant)
        report["decision_outcomes"]=decision_outcomes.summary(_connect,instant)
        decision_quality.attach(report,today)
        decision_outcomes.publish(report,_connect,instant)
        return "PASS_COMPLETED"
    if job=="INVESTMENT_ANALYST_SOURCES":
        from . import investment_analyst,analyst_source_discovery
        if not analyst_source_discovery.enabled():return "DISABLED_OR_NOT_AUTHORIZED"
        instant=now()
        report=investment_analyst.analyze(read_snapshot(),instant.astimezone(ZoneInfo("Asia/Kolkata")).date(),instant)
        return "PASS_COMPLETED" if analyst_source_discovery.refresh(report,_connect,instant) else "WAITING_EVIDENCE"
    if job=="INVESTMENT_ANALYST_AI":
        from . import investment_analyst,analyst_committee
        if not automatic_ai_review.providers():return "DISABLED_OR_NOT_AUTHORIZED"
        instant=now()
        report=investment_analyst.analyze(read_snapshot(),instant.astimezone(ZoneInfo("Asia/Kolkata")).date(),instant)
        return "PASS_COMPLETED" if analyst_committee.refresh(report,_connect,instant) else "WAITING_EVIDENCE"
    if job=="AI_REVIEW" and (not automatic_ai_review.enabled() or not automatic_ai_review.providers()):
        return "DISABLED_OR_NOT_AUTHORIZED"
    # AI review intentionally uses the complete enriched snapshot. All other
    # consumers below operate exclusively on NSE/BSE sections.
    snapshot=read_snapshot() if job=="AI_REVIEW" else read_market_snapshot()
    if not snapshot["enabled"]:
        return "DISABLED_OR_NOT_AUTHORIZED"
    # Previously published mature watches still need outcome evaluation even
    # when today's discovery failed; new publication uses READY sections only.
    if job=="WATCH_OUTCOMES":
        # Apply cached positive independent cautions before publication.
        # A failed optional surveillance read must not prevent existing
        # mature-watch evaluation or silently clear a new FIP publication.
        try:
            current=now()
            nse_surveillance.attach(snapshot,_connect,current)
            fip_research.publish(snapshot,_connect,current)
        except (ValueError,TypeError,OSError,sqlite3.Error):pass
        watch_outcomes.refresh(snapshot,_connect)
        return "PASS_COMPLETED"
    if job=="COMPANY_EVIDENCE":
        followups=forward_earnings.due_identities(_connect,now())
        if not followups and not any(s["section"] in ("NSE","BSE") and s["status"]=="READY" for s in snapshot["sections"]):
            return "WAITING_EVIDENCE"
        outcome=automatic_company_evidence.refresh(snapshot,_connect,followup_isins=followups) if followups else automatic_company_evidence.refresh(snapshot,_connect)
        return "PASS_COMPLETED" if outcome in ("AVAILABLE","PARTIAL") else "WAITING_EVIDENCE"
    if not any(s["section"] in ("NSE","BSE") and s["status"]=="READY" for s in snapshot["sections"]):
        return "WAITING_EVIDENCE"
    if job=="COMPANY_NEWS":
        automatic_news.refresh(snapshot,_connect)
    elif job=="STRATEGY_REPLAY":
        automatic_strategy_validation.refresh(snapshot,_connect)
    elif job=="AI_REVIEW":
        # Same cached public evidence assembly as the dashboard; no extra provider calls.
        automatic_ai_review.refresh(snapshot,_connect)
    else:
        raise ValueError("UNKNOWN_RESEARCH_JOB")
    return "PASS_COMPLETED"


def company_success_interval(interval):
    """Bounded stock/fund company acquisition cadence; only successful evidence passes.

    One company per pass, single local worker, existing transport cooldowns.
    Invalid operator configuration falls back to the normal job cadence.
    """
    try:
        configured=int(os.getenv("ATLAS_COMPANY_RESEARCH_INTERVAL_SECONDS","300"))
        if not 300<=configured<=86400:return interval
        return configured
    except (ValueError,TypeError):return interval


def run_one_job(interval):
    """Claim one due job, run it outside the transaction, persist its result."""
    claimed=research_jobs.claim(_connect,research_jobs.definitions(SECTIONS),now().timestamp())
    if claimed is None:
        return False
    job,token=claimed
    try:
        outcome=_execute_job(job)
    except global_macro.GlobalCooldown:
        outcome="WAITING_EVIDENCE"
    except Exception:
        outcome="FAILED"
    research_jobs.finish(_connect,job,token,now().timestamp(),(company_success_interval(interval) if job in ("COMPANY_EVIDENCE","FUND_COMPANY_EVIDENCE") and outcome=="PASS_COMPLETED" else research_calendar.POLL_SECONDS if job=="CALENDAR_CONTEXT" else economic_calendar.INTERVAL if job=="ECONOMIC_CALENDAR" and outcome!="DISABLED_OR_NOT_AUTHORIZED" else global_releases.INTERVAL if job in global_releases.JOBS and outcome!="DISABLED_OR_NOT_AUTHORIZED" else global_markets.INTERVAL if job in global_markets.JOBS and outcome!="DISABLED_OR_NOT_AUTHORIZED" else global_macro.INTERVAL if job in global_macro.JOBS and outcome!="DISABLED_OR_NOT_AUTHORIZED" else global_fx.INTERVAL if job=="GLOBAL_FX" and outcome!="DISABLED_OR_NOT_AUTHORIZED" else 3600 if job=="FORWARD_EARNINGS_BASELINE" else 900 if job in ("OFFICIAL_TRI_DOWNLOAD","OFFICIAL_AMFI_TER") else sector_benchmarks.INTERVAL if job=="SECTOR_BENCHMARKS" else nse_financial_filings.INTERVAL if job=="NSE_FINANCIAL_FILINGS" else nse_pledge_filings.INTERVAL if job=="NSE_PLEDGE_FILINGS" else nse_surveillance.INTERVAL if job=="NSE_SURVEILLANCE" else amfi_equity_caps.INTERVAL if job=="AMFI_EQUITY_CAP" else fund_disclosures.INTERVAL if job in ("FUND_DISCLOSURES","FUND_PORTFOLIOS") and outcome!="DISABLED_OR_NOT_AUTHORIZED" else interval),outcome)
    return True


class ResearchScheduler:
    def __init__(self):
        self.task=None
        self.stopping=None

    async def start(self):
        enabled,interval=config()
        if enabled and self.task is None:
            self.stopping=asyncio.Event()
            self.task=asyncio.create_task(self._loop(interval))

    async def _loop(self,interval):
        while not self.stopping.is_set():
            try:
                worked=await asyncio.to_thread(run_one_job,interval)
            except Exception:
                # Storage outage: retry with bounded idle polling rather than spin.
                worked=False
            if not worked:
                try:
                    await asyncio.wait_for(self.stopping.wait(),timeout=research_jobs.POLL_SECONDS)
                except asyncio.TimeoutError:
                    pass

    async def stop(self):
        if self.task is not None:
            self.stopping.set()
            # Do not cancel a worker thread mid-write. Stop after the current
            # bounded job, not after the entire former serial research pass.
            await self.task
            self.task=None


scheduler=ResearchScheduler()
