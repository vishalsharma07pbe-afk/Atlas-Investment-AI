"""Bounded authorized company research, independent of portfolio identity.

Retrieval dates are not financial-period dates. Cached evidence never qualifies
a recommendation or establishes fair value.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from math import isfinite
from zoneinfo import ZoneInfo
import json
import os
import re

from .p1_research import company_research
from .financial_trends import summarize as financial_trends, earnings_evidence
from .fundamental_quality import summarize as fundamental_quality
from .financial_strength import summarize as financial_strength, DETAIL_NAMES
from .earnings_quality import summarize as earnings_quality, INCOME_NAMES
from . import peer_research, shareholding_research
from .corporate_action_normalization import normalize_reported_actions

ISIN = re.compile(r"^IN[A-Z0-9]{10}$")
HORIZONS = ("LONG_TERM", "SHORT_TERM", "SWING")
SECTIONS = ("profile","ratios","income_statement","balance_sheet","cash_flow","shareholding","corporate_actions","competitors")
NORMALIZATION_VERSION=2
ANNUAL_HISTORY_CACHE_DAYS=7
ANNUAL_SECTIONS=("income_statement","balance_sheet","cash_flow")
MAX_PRIORITY_STREAK=3
REFRESH_OUTCOMES=("NO_CANDIDATES","PROVIDER_COOLDOWN","NO_DUE_CANDIDATES","CLAIM_NOT_ACQUIRED","AVAILABLE","PARTIAL","UNAVAILABLE")


def permitted():
    return (os.getenv("ATLAS_AUTOMATIC_COMPANY_RESEARCH_ENABLED","false").lower()=="true"
            and os.getenv("MARKET_DATA_USAGE_RIGHTS_CONFIRMED","false").lower()=="true"
            and os.getenv("MARKET_DATA_ENTITLEMENT_CONFIRMED","false").lower()=="true"
            and bool(os.getenv("UPSTOX_ACCESS_TOKEN","").strip()))


def identify(snapshot):
    for section in snapshot["sections"]:
        if section["status"]!="READY" or section["section"] not in ("NSE","BSE"):
            continue
        for horizon in HORIZONS:
            for item in (section.get("result") or {}).get("horizons",{}).get(horizon,{}).get("candidates",[]):
                isin=item.get("isin")
                if isinstance(isin,str) and ISIN.fullmatch(isin) and item.get("exchange")==section["section"]:
                    yield item,isin


def identify_priority(snapshot):
    yield from identify(snapshot)
    # Deepen the actual Elite candidates without expanding report attachment.
    for section in snapshot.get("sections",[]):
        if section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):
            continue
        result=section.get("result") or {}
        coverage=result.get("discovery_coverage") or {}
        expected=coverage.get("expected_session")
        if coverage.get("calendar_status")=="PUBLISHED_SESSION" and expected:
            for item in result.get("steady_momentum_candidates",[]):
                isin=item.get("isin")
                if isinstance(isin,str) and ISIN.fullmatch(isin) and item.get("exchange")==section["section"] and item.get("as_of")==expected and item.get("security_state") not in ("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED"):
                    yield item,isin


def identify_sample(snapshot,instant):
    """Only validated completed public histories from the bounded discovery sample."""
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    for section in snapshot.get("sections",[]):
        exchange=section.get("section")
        if exchange not in ("NSE","BSE") or section.get("status")!="READY":
            continue
        result=section.get("result") or {}
        rows=result.get("company_research_universe")
        if not isinstance(rows,list) or len(rows)>20000:
            continue
        count=result.get("eligible_count")
        if type(count) is not int or not len(rows)<=count<=20000:
            continue
        ids=[r.get("id") for r in rows if isinstance(r,dict)]
        if any(type(i) is not int or i<=0 for i in ids) or len(ids)!=len(rows) or len(set(ids))!=len(ids):
            continue
        for row in rows:
            isin=row.get("isin")
            if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or row.get("exchange")!=exchange:
                continue
            try:
                observed=datetime.strptime(row.get("as_of",""),"%Y-%m-%d").date()
            except (ValueError,TypeError):
                continue
            if 1<=(today-observed).days<=4:
                yield exchange,isin


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_company_evidence(
        isin TEXT PRIMARY KEY, attempted_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL,
        status TEXT NOT NULL, payload TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_company_annual_archive(
        isin TEXT PRIMARY KEY, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_company_rotation(
        scope TEXT PRIMARY KEY, priority_streak INTEGER NOT NULL)""")


def annual_capture(report,isin,instant):
    """One coherent exact-source annual capture, never refreshed by a cache read."""
    try:
        if not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or report.get("isin")!=isin:
            return None
        stamp=datetime.fromisoformat(report["retrieved_at"])
        if stamp.tzinfo is None or not instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)<=stamp<=instant:
            return None
        from .financial_strength import _block
        sections={}
        for key in ANNUAL_SECTIONS:
            data,source=_block(report,key)
            if data and source and data.get("rows") and datetime.fromisoformat(source["retrieved_at"])==stamp:
                sections[key]=report["sections"][key]
        if not sections:
            return None
        return {"isin":isin,"retrieved_at":stamp.isoformat(),"sections":sections,
                "available_sections":len(sections),"historical_cache_only":True,
                "notice":"Retained exact-source annual capture only. Not fresh company evidence or a forward estimate."}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return None


def _archive(db,report,isin,instant):
    captured=annual_capture(report,isin,instant)
    if captured:
        db.execute("""INSERT INTO automatic_company_annual_archive VALUES(?,?,?)
            ON CONFLICT(isin) DO UPDATE SET retrieved_at=excluded.retrieved_at,payload=excluded.payload
            WHERE automatic_company_annual_archive.retrieved_at<=excluded.retrieved_at""",
            (isin,captured["retrieved_at"],json.dumps(captured,allow_nan=False)))


def text(value):
    return value.strip()[:180] if isinstance(value,str) else None


def number(value):
    if isinstance(value,bool) or value is None:
        return None
    try:
        n=float(str(value).strip().rstrip("%"))
        return n if isfinite(n) else None
    except (TypeError,ValueError,OverflowError):
        return None


def history(rows, category="category"):
    result=[]
    for row in rows[:40] if isinstance(rows,list) else []:
        if not isinstance(row,dict) or not text(row.get(category)):
            continue
        points=[]
        raw=row.get("history")
        for point in raw[:5] if isinstance(raw,list) else []:
            if not isinstance(point,dict):
                continue
            period=text(point.get("period"))
            value=number(point.get("value"))
            if period and value is not None:
                points.append({"period":period,"value":value})
        if points:
            result.append({"name":text(row[category]),"history":points})
    return result


def normalize(report, isin, instant):
    if report.get("isin")!=isin or not isinstance(report.get("sections"),dict):
        raise ValueError("COMPANY_IDENTITY_MISMATCH")
    sections={}
    for key in SECTIONS:
        section=report["sections"].get(key) or {}
        raw=section.get("data") if section.get("status")=="AVAILABLE" else None
        data=None
        if key=="profile" and isinstance(raw,dict):
            data={k:text(raw.get(k)) for k in ("sector","industry","company_name","company_profile") if text(raw.get(k))}
        elif key=="ratios" and isinstance(raw,list):
            data=[]
            for r in raw[:50]:
                if not isinstance(r,dict) or not text(r.get("name")):
                    continue
                company=number(r.get("company_value"))
                sector=number(r.get("sector_value"))
                if company is not None:
                    data.append({"name":text(r["name"]),"company_value":company,"sector_value":sector,
                                 "unit":r.get("unit") if r.get("unit") in ("PERCENT","RATIO") else "UNKNOWN",
                                 "sector_unit":r.get("sector_unit") if r.get("sector_unit") in ("PERCENT","RATIO") else "UNKNOWN"})
        elif key in ("income_statement","cash_flow") and isinstance(raw,dict):
            rows=history(raw.get(key))
            if rows:
                data={"units":text(raw.get("units_in")),"rows":rows,
                      "statement_type":text(raw.get("type")),"time_period":text(raw.get("time_period"))}
                if key=="cash_flow" and data["statement_type"]=="consolidated" and data["time_period"]=="yearly":
                    data["detail_rows"]=[r for r in history(raw.get("full_statement"),category="particular")
                                         if r["name"].strip().casefold() in DETAIL_NAMES["cash_flow"]]
                if key=="income_statement" and data["statement_type"]=="consolidated" and data["time_period"]=="yearly":
                    # Full statement EPS lines have a different dimensional meaning
                    # from the aggregate monetary statement. Do not apply crore units.
                    detailed=history(raw.get("full_statement"),category="particular")
                    data["eps_rows"]=[r for r in detailed if r["name"].strip().casefold() in ("eps - basic","eps - diluted")]
                    data["detail_rows"]=[r for r in detailed if r["name"].strip().casefold() in INCOME_NAMES]
        elif key=="balance_sheet" and isinstance(raw,dict):
            rows=[]
            for point in raw.get("history",[])[:5] if isinstance(raw.get("history"),list) else []:
                if not isinstance(point,dict) or not text(point.get("period")):
                    continue
                values={k:number(point.get(k)) for k in ("total_asset","total_liability")}
                if any(v is not None for v in values.values()):
                    rows.append({"period":text(point["period"]),**values})
            if rows:
                data={"units":text(raw.get("units_in")),"rows":rows,
                      "statement_type":text(raw.get("type")),"time_period":text(raw.get("time_period"))}
                if data["statement_type"]=="consolidated" and data["time_period"]=="yearly":
                    data["detail_rows"]=[r for r in history(raw.get("full_statement"),category="particular")
                                         if r["name"].strip().casefold() in DETAIL_NAMES["balance_sheet"]]
        elif key=="shareholding":
            data=history(raw)
        elif key=="competitors" and isinstance(raw,list):
            data=[]
            for row in raw[:30]:
                if not isinstance(row,dict):
                    continue
                instrument=row.get("instrument_key")
                match=peer_research.KEY.fullmatch(instrument) if isinstance(instrument,str) else None
                name=text(row.get("name") or row.get("company_name"))
                if match and match.group(2)!=isin:
                    data.append({"name":name or match.group(2),"instrument_key":instrument,"sector":text(row.get("sector"))})
                elif name and not instrument:
                    data.append({"name":name,"sector":text(row.get("sector"))})
        elif key=="corporate_actions" and isinstance(raw,list):
            data=normalize_reported_actions(raw)
        source=section.get("source")
        endpoint=source.get("endpoint") if isinstance(source,dict) else None
        # Existing adapter supplies fixed public paths, never persist arbitrary URLs.
        if not isinstance(endpoint,str) or not re.fullmatch(r"/v2/fundamentals/[A-Z0-9%|._-]+/[a-z-]+",endpoint):
            endpoint=None
        sections[key]={"status":"AVAILABLE" if data else "UNAVAILABLE","data":data or None,
                       "source":{"provider":"UPSTOX","endpoint":endpoint,"retrieved_at":instant.isoformat()} if data else None}
        if not data:
            # Keep only fixed error labels; no raw HTTP messages or tokens.
            error=section.get("error")
            allowed={"NO_PROVIDER_RECORDS","PROVIDER_REQUEST_REJECTED","PROVIDER_HTTP_FAILURE",
                     "PROVIDER_ACCESS_REJECTED","PROVIDER_RATE_LIMITED","PROVIDER_RECOVERY_COOLDOWN",
                     "PROVIDER_RESPONSE_TOO_LARGE","PROVIDER_SCHEMA_INVALID","UPSTOX_SCHEMA_MISMATCH",
                     "PROVIDER_REQUEST_FAILED","RECOVERY_STORAGE_UNAVAILABLE","UPSTOX_TOKEN_MISSING",
                     "UPSTOX_RATIO_SCHEMA_INVALID"}
            sections[key]["diagnostic"]=error if isinstance(error,str) and error in allowed else (
                "UNSUPPORTED_OR_EMPTY_NORMALIZED_DATA" if section.get("status")=="AVAILABLE" else "UNAVAILABLE_REASON_UNKNOWN")
            if key=="competitors" and endpoint in (f"/v2/fundamentals/{isin}/competitors",
                f"/v2/fundamentals/NSE_EQ%7C{isin}/competitors",f"/v2/fundamentals/BSE_EQ%7C{isin}/competitors"):
                sections[key]["attempted_endpoint"]=endpoint
    available=sum(s["status"]=="AVAILABLE" for s in sections.values())
    return {"isin":isin,"retrieved_at":instant.isoformat(),"normalization_version":NORMALIZATION_VERSION,"sections":sections,
            "available_sections":available,"total_sections":len(SECTIONS),
            "notice":"Provider-reported evidence, not independently reconciled with filings. Ratio observation periods may be unspecified. Sector ratios are comparisons, not fair value."}


def _legacy(row):
    if not row or row["status"] not in ("AVAILABLE","PARTIAL") or not row["payload"]:
        return False
    try:
        report=json.loads(row["payload"])
        return report.get("isin")==row["isin"] and report.get("normalization_version")!=NORMALIZATION_VERSION
    except (ValueError,TypeError,AttributeError,KeyError):
        return False


def _refresh_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_company_refresh_state(
        scope TEXT PRIMARY KEY, observed_at TEXT NOT NULL, outcome TEXT NOT NULL)""")


def refresh(snapshot, connect, loader=company_research, instant=None, *, explicit_isins=None):
    if not snapshot["enabled"] or not permitted():
        return
    instant=instant or datetime.now(timezone.utc)
    outcome=_refresh(snapshot,connect,loader,instant,explicit_isins=explicit_isins)
    scope="FUND" if explicit_isins is not None else "STOCK"
    with closing(connect()) as db,db:
        _refresh_table(db)
        db.execute("""INSERT INTO automatic_company_refresh_state VALUES(?,?,?)
            ON CONFLICT(scope) DO UPDATE SET observed_at=excluded.observed_at,outcome=excluded.outcome
            WHERE automatic_company_refresh_state.observed_at<=excluded.observed_at""",
            (scope,instant.isoformat(),outcome))
    return outcome


def _refresh(snapshot, connect, loader, instant, *, explicit_isins=None):
    stamp=instant.isoformat()
    candidates={}
    for item,isin in identify_priority(snapshot):
        # Exact public discovery venue/ISIN; no name matching.
        if isin not in candidates or item["exchange"]=="NSE":
            candidates[isin]=item["exchange"]+"_EQ|"+isin
    if explicit_isins is not None:
        # The documented fundamentals adapter accepts ISIN without an exchange key.
        # This input is used only for bounded, public, exact as-filed fund equities.
        candidates={i:None for i in explicit_isins[:200] if isinstance(i,str) and re.fullmatch(r"INE[A-Z0-9]{9}",i)}
    sample={}
    if explicit_isins is None:
        for exchange,isin in identify_sample(snapshot,instant):
            if isin not in sample or exchange=="NSE":
                sample[isin]=exchange+"_EQ|"+isin
    if not candidates and not sample:
        return "NO_CANDIDATES"
    with closing(connect()) as db, db:
        _table(db)
        rows={r["isin"]:r for r in db.execute("SELECT isin,attempted_at,next_attempt_at,status,payload FROM automatic_company_evidence")}
        # Avoid repeated requests across the universe when the provider rejects access.
        if any(r["status"]=="UNAVAILABLE" and r["attempted_at"]>(instant-timedelta(hours=1)).isoformat() for r in rows.values()):
            return "PROVIDER_COOLDOWN"
        priority={isin:i for i,isin in enumerate(candidates)} if explicit_isins is not None else {}
        def due_now(i):
            return i not in rows or rows[i]["next_attempt_at"]<=stamp
        due=sorted((isin for isin in candidates if due_now(isin)),
                   key=lambda isin:(rows[isin]["attempted_at"] if isin in rows else "",priority.get(isin,0),isin))
        broad=False
        streak=0
        if explicit_isins is None:
            rotation=db.execute("SELECT priority_streak FROM automatic_company_rotation WHERE scope='STOCK'").fetchone()
            streak=rotation["priority_streak"] if rotation else 0
            peers=peer_candidates(rows,candidates,instant)
            peer_due=sorted((i for i in peers if due_now(i)),
                            key=lambda i:(rows[i]["attempted_at"] if i in rows else "",i))
            sample_due=sorted((i for i in sample if i not in candidates and i not in peers and due_now(i)),
                              key=lambda i:(0 if _legacy(rows.get(i)) else 1,
                                            rows[i]["attempted_at"] if i in rows else "",i))
            # Reserve one bounded pass after three priority claims when broad
            # work is due. Never increase the request budget or bypass due gates.
            if sample_due and (streak>=MAX_PRIORITY_STREAK or not (due or peer_due)):
                due=sample_due
                candidates.update(sample)
                broad=True
            elif not due and peer_due:
                due=peer_due
                candidates.update(peers)
        if not due:
            return "NO_DUE_CANDIDATES"
        isin=due[0]
        claim=db.execute("""INSERT INTO automatic_company_evidence VALUES(?,?,?,'RUNNING',NULL)
            ON CONFLICT(isin) DO UPDATE SET attempted_at=excluded.attempted_at,
            next_attempt_at=excluded.next_attempt_at,status='RUNNING',payload=NULL
            WHERE automatic_company_evidence.next_attempt_at<=?""",
            (isin,stamp,(instant+timedelta(hours=6)).isoformat(),stamp))
        if claim.rowcount!=1:
            return "CLAIM_NOT_ACQUIRED"
        previous=rows.get(isin)
        if previous and previous["status"] in ("AVAILABLE","PARTIAL") and previous["payload"]:
            try:
                _archive(db,json.loads(previous["payload"]),isin,instant)
            except (ValueError,TypeError,AttributeError):
                pass
        if explicit_isins is None:
            db.execute("""INSERT INTO automatic_company_rotation VALUES('STOCK',?)
                ON CONFLICT(scope) DO UPDATE SET priority_streak=excluded.priority_streak""",
                (0 if broad else min(MAX_PRIORITY_STREAK,streak+1),))
    try:
        report=normalize(loader(isin,candidates[isin]),isin,instant)
        status="AVAILABLE" if report["available_sections"]==len(SECTIONS) else "PARTIAL" if report["available_sections"] else "UNAVAILABLE"
    except Exception:
        report={"isin":isin,"retrieved_at":stamp,"normalization_version":NORMALIZATION_VERSION,
                "available_sections":0,"total_sections":len(SECTIONS),
                "sections":{key:{"status":"UNAVAILABLE","data":None,"source":None,
                    "diagnostic":"COLLECTION_OR_NORMALIZATION_FAILED"} for key in SECTIONS}}
        status="UNAVAILABLE"
    with closing(connect()) as db, db:
        updated=db.execute("""UPDATE automatic_company_evidence SET status=?,payload=?,next_attempt_at=?
            WHERE isin=? AND attempted_at=? AND status='RUNNING'""",
            (status,json.dumps(report,allow_nan=False),
             (instant+timedelta(hours=24 if status=="AVAILABLE" else 6)).isoformat(),isin,stamp))
        if updated.rowcount==1 and status!="UNAVAILABLE":
            _archive(db,report,isin,instant)
        db.execute("DELETE FROM automatic_company_evidence WHERE attempted_at<?",((instant-timedelta(days=30)).isoformat(),))
        db.execute("DELETE FROM automatic_company_annual_archive WHERE retrieved_at<?",((instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)).isoformat(),))
    return status


def acquisition_status(snapshot,connect,instant):
    """Aggregate local-only diagnostics. No requests, payloads or identifiers."""
    if not snapshot.get("enabled") or not permitted():
        return {"status":"DISABLED_OR_NOT_AUTHORIZED"}
    import sqlite3
    from collections import Counter
    sample={isin for _,isin in identify_sample(snapshot,instant)}
    primary={isin for _,isin in identify_priority(snapshot)}
    stamp=instant.isoformat()
    try:
        with closing(connect()) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('automatic_company_evidence','automatic_company_refresh_state','automatic_company_annual_archive','automatic_company_rotation')")}
            rows={r["isin"]:r for r in db.execute("SELECT * FROM automatic_company_evidence")} if "automatic_company_evidence" in tables else {}
            archived={}
            if "automatic_company_annual_archive" in tables:
                for row in db.execute("SELECT * FROM automatic_company_annual_archive WHERE retrieved_at BETWEEN ? AND ?",
                                      ((instant-timedelta(days=ANNUAL_HISTORY_CACHE_DAYS)).isoformat(),stamp)):
                    if row["isin"] in sample:
                        try:
                            captured=annual_capture(json.loads(row["payload"]),row["isin"],instant)
                            if captured:
                                archived[row["isin"]]=captured
                        except (ValueError,TypeError,AttributeError):
                            continue
            rotation=db.execute("SELECT priority_streak FROM automatic_company_rotation WHERE scope='STOCK'").fetchone() if "automatic_company_rotation" in tables else None
            outcomes={}
            if "automatic_company_refresh_state" in tables:
                for row in db.execute("SELECT * FROM automatic_company_refresh_state"):
                    if row["scope"] in ("STOCK","FUND") and row["outcome"] in REFRESH_OUTCOMES:
                        observed=datetime.fromisoformat(row["observed_at"])
                        if observed.tzinfo is not None and observed<=instant:
                            outcomes[row["scope"]]={"observed_at":observed.isoformat(),"outcome":row["outcome"]}
        def due(isin):
            return isin not in rows or rows[isin]["next_attempt_at"]<=stamp
        counts=Counter()
        sections=Counter()
        detail=Counter()
        diagnostic_counts={key:Counter() for key in SECTIONS}
        allowed_diagnostics={"NO_PROVIDER_RECORDS","PROVIDER_REQUEST_REJECTED","PROVIDER_HTTP_FAILURE",
            "PROVIDER_ACCESS_REJECTED","PROVIDER_RATE_LIMITED","PROVIDER_RECOVERY_COOLDOWN",
            "PROVIDER_RESPONSE_TOO_LARGE","PROVIDER_SCHEMA_INVALID","UPSTOX_SCHEMA_MISMATCH",
            "PROVIDER_REQUEST_FAILED","RECOVERY_STORAGE_UNAVAILABLE","UPSTOX_TOKEN_MISSING",
            "UPSTOX_RATIO_SCHEMA_INVALID","UNSUPPORTED_OR_EMPTY_NORMALIZED_DATA",
            "UNAVAILABLE_REASON_UNKNOWN","COLLECTION_OR_NORMALIZATION_FAILED"}
        for isin in sample:
            row=rows.get(isin)
            if not row:
                counts["never_attempted"]+=1
                continue
            if row["status"] not in ("AVAILABLE","PARTIAL","UNAVAILABLE","RUNNING"):
                counts["unknown_status"]+=1
                continue
            counts[row["status"].lower()]+=1
            if _legacy(row):
                counts["legacy_reports"]+=1
                if due(isin):
                    counts["due_legacy_reports"]+=1
            if row["status"] not in ("AVAILABLE","PARTIAL","UNAVAILABLE") or not row["payload"]:
                continue
            try:
                report=json.loads(row["payload"])
                retrieved=datetime.fromisoformat(report["retrieved_at"])
                if report.get("isin")!=isin or retrieved.tzinfo is None or not instant-timedelta(hours=24)<=retrieved<=instant:
                    continue
                for key in SECTIONS:
                    block=report["sections"].get(key) or {}
                    if block.get("status")=="UNAVAILABLE":
                        reason=block.get("diagnostic")
                        diagnostic_counts[key][reason if isinstance(reason,str) and reason in allowed_diagnostics else "UNAVAILABLE_REASON_UNKNOWN"]+=1
                if row["status"]=="UNAVAILABLE":
                    continue
                counts["fresh_reports"]+=1
                if report.get("normalization_version")==NORMALIZATION_VERSION:
                    counts["fresh_current_normalization"]+=1
                for key in SECTIONS:
                    block=report["sections"].get(key) or {}
                    if block.get("status")=="AVAILABLE" and block.get("data"):
                        sections[key]+=1
                        if key in ("income_statement","balance_sheet","cash_flow") and isinstance(block["data"],dict) and block["data"].get("detail_rows"):
                            detail[key]+=1
            except (ValueError,TypeError,AttributeError,KeyError,OverflowError):
                continue
        return {"status":"LOCAL_ACQUISITION_AUDIT","sample_identities":len(sample),
                "primary_identities":len(primary),"due_sample":sum(due(i) for i in sample),
                "due_primary":sum(due(i) for i in primary),"counts":dict(counts),
                "fresh_sections":dict(sections),"fresh_detailed_statements":dict(detail),
                "annual_archive_companies":len(archived),
                "annual_archive_section_counts":dict(Counter(key for capture in archived.values() for key in capture["sections"])),
                "priority_streak":rotation["priority_streak"] if rotation else 0,
                "recent_section_diagnostics":{k:dict(v) for k,v in diagnostic_counts.items() if v},
                "global_company_cooldown":any(r["status"]=="UNAVAILABLE" and r["attempted_at"]>(instant-timedelta(hours=1)).isoformat() for r in rows.values()),
                "last_passes":outcomes,
                "notice":"Latest bounded pass outcomes and validated sample coverage, not full market coverage. A completed scheduler pass may have made no request."}
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return {"status":"ACQUISITION_AUDIT_UNAVAILABLE"}


def peer_candidates(rows,primary,instant):
    result={}
    oldest=(instant-timedelta(hours=24)).isoformat()
    latest=instant.isoformat()
    for isin in sorted(primary):
        row=rows.get(isin)
        if not row or row["status"] not in ("AVAILABLE","PARTIAL") or not oldest<=row["attempted_at"]<=latest or not row["payload"]:
            continue
        try:
            report=json.loads(row["payload"])
            if report.get("isin")!=isin:
                continue
            for peer,key in peer_research.selected(report):
                if peer not in primary:
                    result.setdefault(peer,key)
                if len(result)>=peer_research.MAX_ROTATION:
                    return result
        except (ValueError,TypeError,AttributeError):
            continue
    return result


def cached_action_reports(connect,identities,instant):
    """Bounded public exact-ISIN cache read; no network or personal data."""
    if not permitted():
        return {}
    wanted={i for i in identities if isinstance(i,str) and re.fullmatch(r"INE[A-Z0-9]{9}",i)}
    if not wanted or len(wanted)>200:
        return {}
    try:
        with closing(connect()) as db:
            marks=",".join("?" for _ in wanted)
            rows=db.execute(f"""SELECT isin,payload FROM automatic_company_evidence
                WHERE isin IN ({marks}) AND status IN ('AVAILABLE','PARTIAL')
                AND attempted_at BETWEEN ? AND ?""",(*sorted(wanted),(instant-timedelta(hours=24)).isoformat(),instant.isoformat())).fetchall()
        result={}
        for row in rows:
            try:
                report=json.loads(row["payload"])
                if report.get("isin")==row["isin"]:
                    result[row["isin"]]=report
            except (ValueError,TypeError,AttributeError,KeyError):
                continue
        return result
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {}
    except __import__("sqlite3").Error:
        return {}


def _enrich(report,today):
    report["financial_trends"]=financial_trends(report,today.year,as_of=today)
    report["reported_earnings"]=earnings_evidence(report,today)
    report["fundamental_quality"]=fundamental_quality(report,today.year)
    report["financial_strength"]=financial_strength(report,today)
    report["earnings_quality"]=earnings_quality(report,today)
    report["ownership_research"]=shareholding_research.summarize(report,today)
    return report


def attach(snapshot,connect,instant=None):
    snapshot["automatic_company_status"]="DISABLED_OR_NOT_AUTHORIZED"
    if not snapshot["enabled"] or not permitted():
        return snapshot
    snapshot["automatic_company_status"]="ENABLED"
    instant=instant or datetime.now(timezone.utc)
    with closing(connect()) as db:
        _table(db)
        rows={r["isin"]:r for r in db.execute("SELECT * FROM automatic_company_evidence WHERE status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?",
              ((instant-timedelta(hours=24)).isoformat(),instant.isoformat()))}
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    # Coverage counts are distinct public identities, not qualified stocks.
    sample_by_exchange={exchange:set() for exchange in ("NSE","BSE")}
    for exchange,isin in identify_sample(snapshot,instant):
        sample_by_exchange[exchange].add(isin)
    for section in snapshot["sections"]:
        if section.get("section") not in sample_by_exchange or section.get("status")!="READY":
            continue
        result=section.get("result") or {}
        if not isinstance(result.get("company_research_universe"),list):
            continue
        sample=sample_by_exchange[section["section"]]
        cached=0
        section_counts={k:0 for k in SECTIONS}
        for isin in sample:
            row=rows.get(isin)
            if not row or not row["payload"]:
                continue
            try:
                report=json.loads(row["payload"])
                stamp=datetime.fromisoformat(report["retrieved_at"])
                if report.get("isin")!=isin or stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant:
                    continue
                available=[k for k in SECTIONS if (report.get("sections",{}).get(k) or {}).get("status")=="AVAILABLE"
                           and (report.get("sections",{}).get(k) or {}).get("data")]
                if available:
                    cached+=1
                    for k in available:
                        section_counts[k]+=1
            except (ValueError,TypeError,KeyError,AttributeError):
                continue
        result["company_research_coverage"]={"distinct_eligible_isins":len(sample),"fresh_cached_reports":cached,
            "section_counts":section_counts,"notice":"Distinct eligible public identities in this exchange sample; provider-reported evidence only, not full market coverage or qualified recommendations."}
    # Build bounded sector/industry cohorts from the already cached
    # validated discovery sample, not a fabricated provider competitor list.
    cohort={}
    sample_keys={}
    for exchange,isin in identify_sample(snapshot,instant):
        if isin not in sample_keys or exchange=="NSE":
            sample_keys[isin]=exchange+"_EQ|"+isin
    for isin,key in sample_keys.items():
        row=rows.get(isin)
        if not row or not row["payload"]:
            continue
        try:
            report=json.loads(row["payload"])
            if report.get("isin")==isin and peer_research.fresh_sector(report,instant):
                cohort[isin]=(key,_enrich(report,today))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            continue
    # Enrich only primary identities and their explicitly selected one-hop peers.
    primary=list(identify(snapshot))
    wanted={isin for _,isin in primary}
    wanted.update(peer_candidates(rows,wanted,instant))
    reports={}
    for isin in wanted:
        row=rows.get(isin)
        if row and row["payload"]:
            try:
                report=json.loads(row["payload"])
                if report.get("isin")==isin:
                    reports[isin]=_enrich(report,today)
            except (ValueError,TypeError,AttributeError,KeyError,OverflowError):
                continue
    for item,isin in primary:
        report=reports.get(isin)
        if report:
            report["peer_research"]=peer_research.summarize(report,reports)
            report["industry_sample"]=peer_research.industry_sample(report,cohort,instant)
            report["sector_sample"]=peer_research.sector_sample(report,cohort,instant)
            item["company_evidence"]=report
    return snapshot
