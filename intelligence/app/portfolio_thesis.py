"""Private local cache of public company evidence selected by held identities.

Never share this cache with public discovery or public news alerts.
No owner identifiers, holding values, quantities or notes enter Python.
"""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
from math import isfinite
import os
import sqlite3

from . import automatic_company_evidence as company, automatic_news as news, ai_failover, ai_claims
from .market_client import backend_json

NOTICE="Local model assertions checked against supplied public observations only; not independent source verification or an investment verdict."
REVIEW_VERSION="PRIVATE-SCALAR-2"
RATIOS={"p/e":"PE","pe":"PE","price to earnings":"PE","p/b":"PB","price to book":"PB",
        "roe":"ROE","return on equity":"ROE","roce":"ROCE","return on capital employed":"ROCE",
        "debt to equity":"DEBT_EQUITY","debt/equity":"DEBT_EQUITY"}


def enabled():
    return (os.getenv("ATLAS_AUTONOMOUS_RESEARCH_ENABLED","false").lower()=="true"
        and os.getenv("ATLAS_PORTFOLIO_THESIS_ENABLED","false").lower()=="true")


def connect():
    path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3"))
    path=path.with_name("portfolio_"+path.name)
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    return db


def identities(rows):
    if not isinstance(rows,list):
        raise ValueError("INVALID_IDENTITIES")
    unique=set()
    for row in rows[:200]:
        if not isinstance(row,dict):
            continue
        isin,exchange=row.get("isin"),row.get("exchange")
        if isinstance(isin,str) and company.ISIN.fullmatch(isin) and exchange in ("NSE","BSE"):
            unique.add((exchange,isin))
    return sorted(unique)


def selection(rows):
    selected=identities(rows)
    return {"enabled":True,"sections":[{"section":exchange,"status":"READY",
        "result":{"horizons":{"LONG_TERM":{"candidates":[{"isin":isin,"exchange":ex} for ex,isin in selected if ex==exchange]}}}}
        for exchange in ("NSE","BSE")]}


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS portfolio_local_ai(
        evidence_hash TEXT PRIMARY KEY,attempted_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT)""")


def _local_enabled():
    return (enabled() and os.getenv("ATLAS_AUTOMATIC_AI_REVIEW_ENABLED","false").lower()=="true"
            and ai_failover._enabled("OLLAMA") and "OLLAMA" in ai_failover._order())


def _pack(item):
    """Typed, bounded evidence only; no identity or arbitrary provider prose."""
    report=item.get("company_evidence")
    if not isinstance(report,dict) or report.get("isin")!=item.get("isin"):
        return None
    block=(report.get("sections") or {}).get("ratios") or {}
    rows=block.get("data")
    if block.get("status")!="AVAILABLE" or not isinstance(rows,list):
        return None
    grouped={}
    for row in rows[:50]:
        if not isinstance(row,dict) or not isinstance(row.get("name"),str):
            continue
        key=RATIOS.get(row["name"].strip().lower())
        if key:
            grouped.setdefault(key,[]).append(row)
    ratios={}
    for key,entries in sorted(grouped.items()):
        if len(entries)!=1:
            continue
        row=entries[0]
        unit="PERCENT" if key in ("ROE","ROCE") else "RATIO"
        a,b=row.get("company_value"),row.get("sector_value")
        if row.get("unit")!=unit or row.get("sector_unit")!=unit:
            continue
        if not all(type(v) in (int,float) and isfinite(v) and abs(v)<=1e9 for v in (a,b)):
            continue
        if unit=="RATIO" and min(a,b)<=0:
            continue
        ratios[key]={"company":a,"sector":b,"unit":unit}
    if not ratios:
        return None
    topics={}
    articles=(item.get("news_evidence") or {}).get("articles",[])
    for article in articles[:10] if isinstance(articles,list) else []:
        if not isinstance(article,dict) or not isinstance(article.get("topics"),list):
            continue
        for topic in news.TOPICS:
            if topic in article["topics"]:
                topics[topic]=topics.get(topic,0)+1
    return {"RATIOS":ratios,"NEWS":topics,
        "LIMITS":["Provider report periods may be unspecified","News topics are not confirmed events or sentiment",
                  "No independent filing, intrinsic value, execution, or strategy validation"]}


def _identity(pack):
    # Changing the model or supplied numeric evidence requires a new review.
    return sha256(json.dumps({"version":REVIEW_VERSION,"pack":pack,"model":os.getenv("ATLAS_OLLAMA_MODEL","llama3.2")},sort_keys=True,allow_nan=False).encode()).hexdigest()


def _review(items,db_connect,runner,instant):
    if not _local_enabled():
        return
    for item in items:
        pack=_pack(item)
        if pack is None:
            continue
        key=_identity(pack)
        with closing(db_connect()) as db,db:
            _table(db)
            claim=db.execute("""INSERT INTO portfolio_local_ai VALUES(?,?,'RUNNING',NULL)
                ON CONFLICT(evidence_hash) DO UPDATE SET attempted_at=excluded.attempted_at,status='RUNNING',payload=NULL
                WHERE portfolio_local_ai.attempted_at<=?""",(key,instant.isoformat(),(instant-timedelta(hours=24)).isoformat()))
            if claim.rowcount!=1:
                continue
        clean=[]
        try:
            prompt=("Review ONLY supplied public numeric ratios, news-topic counts and evidence limitations. "
                    "Return 1 to 8 findings with statement containing a JSON object encoded as a string "
                    'with exactly path and value, e.g. {"path":"/RATIOS/PE/company","value":20}. '
                    "Use an exact scalar at an existing path; evidence_ids must contain exactly the top-level domain. "
                    "No prose, private inference, predictions, new calculations or trade actions. "
                    "News topics are not confirmed events; ratio periods may be unspecified.\n"
                    +json.dumps(pack,allow_nan=False,ensure_ascii=True))
            result=runner(prompt,list(pack),providers=["OLLAMA"])
            if result.get("status")=="MODEL_GROUNDED" and result.get("provider")=="OLLAMA":
                findings=result["response"]["findings"]
                if isinstance(findings,list) and 1<=len(findings)<=8:
                    audit=ai_claims.audit(pack,findings)
                    clean=audit["findings"]
        except Exception:
            clean=[]
        with closing(db_connect()) as db,db:
            db.execute("UPDATE portfolio_local_ai SET status=?,payload=? WHERE evidence_hash=? AND attempted_at=?",
                ("AVAILABLE" if clean else "UNAVAILABLE",json.dumps(clean) if clean else None,key,instant.isoformat()))
            db.execute("DELETE FROM portfolio_local_ai WHERE attempted_at<?",((instant-timedelta(days=7)).isoformat(),))
        return


def _items(snapshot):
    return [item for item,_ in company.identify(snapshot)]


def _reuse_public_company_reports(db_connect,active_isins,instant):
    """One-way local reuse of independently collected public evidence.

    Read-only public connection. Never publish held identities or select provider
    requests from this function. Preserve private claims, failures and cooldowns.
    """
    if not active_isins or not company.permitted():
        return 0
    path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3")).resolve()
    if not path.is_file():
        return 0
    lower=(instant-timedelta(hours=24)).isoformat()
    upper=instant.isoformat()
    try:
        # Query public reports by freshness, filter exact held identities in
        # memory rather than persist any held-derived selection in public storage.
        with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=2)) as public:
            public.row_factory=sqlite3.Row
            if not public.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='automatic_company_evidence'").fetchone():
                return 0
            reports=[]
            for row in public.execute("""SELECT isin,attempted_at,next_attempt_at,status,payload
                    FROM automatic_company_evidence WHERE status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?""",(lower,upper)):
                if row["isin"] not in active_isins or not row["payload"]:
                    continue
                try:
                    report=json.loads(row["payload"])
                    stamp=datetime.fromisoformat(report["retrieved_at"])
                    if (report.get("isin")!=row["isin"] or stamp.tzinfo is None
                        or not instant-timedelta(hours=24)<=stamp<=instant
                        or report.get("normalization_version")!=company.NORMALIZATION_VERSION
                        or not isinstance(report.get("sections"),dict)
                        or not any(isinstance(s,dict) and s.get("status")=="AVAILABLE" and s.get("data") for s in report["sections"].values())):
                        continue
                    next_attempt=min(max(datetime.fromisoformat(row["next_attempt_at"]),instant),instant+timedelta(hours=24))
                    reports.append((row["isin"],row["attempted_at"],next_attempt.isoformat(),row["status"],row["payload"]))
                except (ValueError,KeyError,TypeError,AttributeError,OverflowError):
                    continue
        with closing(db_connect()) as db,db:
            company._table(db)
            reused=0
            for record in reports:
                # Do not replace a private in-progress attempt, failure/cooldown
                # record, or newer report. Import only exact public evidence.
                reused+=db.execute("""INSERT INTO automatic_company_evidence VALUES(?,?,?,?,?)
                    ON CONFLICT(isin) DO UPDATE SET attempted_at=excluded.attempted_at,
                    next_attempt_at=max(automatic_company_evidence.next_attempt_at,excluded.next_attempt_at),
                    status=excluded.status,payload=excluded.payload
                    WHERE automatic_company_evidence.status IN ('AVAILABLE','PARTIAL')
                    AND automatic_company_evidence.attempted_at<excluded.attempted_at""",record).rowcount
            return reused
    except (sqlite3.Error,OSError):
        return 0


def refresh(db_connect=connect,loader=backend_json,runner=ai_failover.grounded_research,instant=None):
    if not enabled():
        return
    instant=instant or datetime.now(timezone.utc)
    snapshot=selection(loader("/api/v1/portfolio-research-identities"))
    active = identities([{"isin":item["isin"],"exchange":item["exchange"]} for item in _items(snapshot)])
    # Remove evidence for identities no longer selected. The public cache is untouched.
    with closing(db_connect()) as db,db:
        company._table(db)
        news._table(db)
        active_isins={isin for _,isin in active}
        active_keys={ex+"_EQ|"+isin for ex,isin in active}
        records={row["isin"]:row for row in db.execute("SELECT isin,status,attempted_at,payload FROM automatic_company_evidence")}
        # Keep only held identities and their current explicitly selected peers
        # inside the private cache. Never move held-derived selections to public discovery.
        retained=active_isins | set(company.peer_candidates(records,active_isins,instant))
        for row in records.values():
            if row["isin"] not in retained:
                db.execute("DELETE FROM automatic_company_evidence WHERE isin=?",(row["isin"],))
        for row in db.execute("SELECT isin FROM automatic_company_annual_archive").fetchall():
            if row["isin"] not in retained:
                db.execute("DELETE FROM automatic_company_annual_archive WHERE isin=?",(row["isin"],))
        _table(db)
        # Always expire old model records, even when no pack can be reviewed.
        db.execute("DELETE FROM portfolio_local_ai WHERE attempted_at<?",((instant-timedelta(days=7)).isoformat(),))
        if not active_isins:
            db.execute("DELETE FROM portfolio_local_ai")
        for row in db.execute("SELECT instrument_key FROM automatic_news_state").fetchall():
            if row["instrument_key"] not in active_keys:
                db.execute("DELETE FROM automatic_news_state WHERE instrument_key=?",(row["instrument_key"],))
    # Reuse fresh public evidence before spending the private provider budget.
    _reuse_public_company_reports(db_connect,active_isins,instant)
    # Reuse the existing bounded adapters with an isolated private cache.
    company.refresh(snapshot,db_connect,instant=instant)
    news.refresh(snapshot,db_connect,instant=instant)
    company.attach(snapshot,db_connect,instant)
    news.attach(snapshot,db_connect,instant)
    _review(_items(snapshot),db_connect,runner,instant)


def _attach_public_filings(snapshot,instant):
    """Reuse existing independent public filings without writes or acquisition.
    
    Held identities only select evidence in memory. Do not call refresh, update
    public claims, or add holding identities to any public discovery section.
    """
    from . import nse_pledge_filings, nse_financial_filings
    path=Path(os.getenv("ATLAS_RESEARCH_SNAPSHOT_DB","/app/ingestion-data/research_snapshots.sqlite3")).resolve()
    if not path.is_file():
        return
    def readonly():
        db=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=2)
        db.row_factory=sqlite3.Row
        return db
    for adapter,field in ((nse_pledge_filings,"independent_pledge_evidence"),
                          (nse_financial_filings,"independent_financial_evidence")):
        try:
            adapter.attach(snapshot,readonly,instant)
        except (sqlite3.Error,OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
            # An absent table, incompatible cache or malformed source must not
            # suppress the existing private review or leave partial attachments.
            for item in _items(snapshot):
                item.pop(field,None)


def read(rows,db_connect=connect,instant=None):
    if not enabled():
        return {"items":{},"status":"DISABLED"}
    instant=instant or datetime.now(timezone.utc)
    snapshot=selection(rows)
    company.attach(snapshot,db_connect,instant)
    news.attach(snapshot,db_connect,instant)
    _attach_public_filings(snapshot,instant)
    from . import governance_review
    from zoneinfo import ZoneInfo
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    output={}
    local=_local_enabled()
    with closing(db_connect()) as db:
        _table(db)
        for item in _items(snapshot):
            key=item["exchange"]+":"+item["isin"]
            result={"status":"EVIDENCE_AVAILABLE" if item.get("company_evidence") or item.get("news_evidence") else "PENDING_OR_UNAVAILABLE",
                    "company_evidence":item.get("company_evidence"),"news_evidence":item.get("news_evidence"),
                    "ai_status":"PENDING_OR_UNAVAILABLE" if local else "LOCAL_MODEL_NOT_CONFIGURED",
                    "ai_review":None}
            # Company-level filings can follow the exact ISIN across venues.
            # Venue-specific surveillance is not inferred from company filings.
            try:
                governance=governance_review.assess(item,item.get("company_evidence") or {},today)
                result["governance_review"]={**governance,"isin":item["isin"]}
                if governance.get("independent_pledge_evidence") or governance.get("independent_financial_evidence"):
                    result["status"]="EVIDENCE_AVAILABLE"
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
                result["governance_review"]=None
            from . import sector_benchmarks, peer_research
            report=item.get("company_evidence") or {}
            if item["exchange"]=="NSE" and report.get("isin")==item["isin"] and sector_benchmarks.permitted():
                result["sector_benchmark_key"]=sector_benchmarks.mapping(peer_research.fresh_classification(report,instant))
            pack=_pack(item)
            if local and pack is not None:
                cached=db.execute("SELECT * FROM portfolio_local_ai WHERE evidence_hash=? AND status='AVAILABLE' AND attempted_at BETWEEN ? AND ?",
                    (_identity(pack),(instant-timedelta(hours=24)).isoformat(),instant.isoformat())).fetchone()
                if cached:
                    result["ai_status"]="AVAILABLE"
                    result["ai_review"]={"provider":"OLLAMA","reviewed_at":cached["attempted_at"],"findings":json.loads(cached["payload"]),"notice":NOTICE}
            output[key]=result
    return {"items":output,"status":"ENABLED"}


def fund_evidence(rows,instant=None):
    """Exact held Growth scheme metadata, read only from authorized bulk caches.

    No additional provider/model requests, no owner information, no ranking-sample
    restriction. Each scheme keeps the existing disclosure and composition gates.
    """
    from . import fund_disclosures, fund_portfolios
    from zoneinfo import ZoneInfo
    if not enabled() or not fund_disclosures.permitted():
        return {}
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    result={}
    for row in rows[:20]:
        code=row.get("scheme_code")
        if type(code) is not int or str(code) in result or row.get("amfi_option")!="GROWTH":
            continue
        if not fund_disclosures._day(row.get("amfi_metadata_date"),today,7):
            continue
        matches=fund_disclosures.matched([row],today)
        if len(matches)!=1:
            continue
        disclosure=matches[0]
        portfolios=fund_portfolios.matched([disclosure],instant,include_exact_weights=True)
        result[str(code)]={"status":"SECONDARY_REPORTED_EVIDENCE",
            "disclosure":disclosure,"portfolio":portfolios[0] if len(portfolios)==1 else None,
            "notice":"Exact held scheme, secondary reported evidence only; official filings, benchmark history and forward growth remain unverified."}
    return result
