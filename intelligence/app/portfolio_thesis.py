"""Private local cache of public company evidence selected by held identities.

Never share this cache with public discovery or public news alerts.
No owner identifiers, holding values, quantities or notes enter Python.
"""
from contextlib import closing
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3

from . import automatic_company_evidence as company, automatic_news as news, ai_failover
from .automatic_ai_review import UNSAFE
from .market_client import backend_json

NOTICE="Unverified local-model commentary on public evidence, not an investment verdict."
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
    report=item.get("company_evidence")
    if not report:
        return None
    ratios={}
    for row in report["sections"]["ratios"]["data"] or []:
        key=RATIOS.get(row["name"].strip().lower())
        if key:
            ratios[key]={"company":row["company_value"],"sector":row["sector_value"],"unit":row["unit"]}
    if not ratios:
        return None
    topics={}
    for article in (item.get("news_evidence") or {}).get("articles",[]):
        for topic in article["topics"]:
            if topic in news.TOPICS:
                topics[topic]=topics.get(topic,0)+1
    return {"RATIOS":ratios,"NEWS_TOPICS":topics,
        "LIMITS":["Provider report periods may be unspecified","News topics are not confirmed events or sentiment",
                  "No independent filing, intrinsic value, execution, or strategy validation"]}


def _identity(pack):
    # Changing the model or supplied numeric evidence requires a new review.
    return sha256(json.dumps({"pack":pack,"model":os.getenv("ATLAS_OLLAMA_MODEL","llama3.2")},sort_keys=True,allow_nan=False).encode()).hexdigest()


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
            prompt=("Review ONLY public numeric ratios and unverified news-topic counts. "
                    "Describe risks and missing evidence. Do not infer holdings, give trade actions, "
                    "price targets, predictions or probabilities. Cite RATIOS, NEWS_TOPICS or LIMITS. "
                    "Return required JSON.\n"+json.dumps(pack,allow_nan=False))
            result=runner(prompt,list(pack),providers=["OLLAMA"])
            if result.get("status")=="MODEL_GROUNDED" and result.get("provider")=="OLLAMA":
                findings=result["response"]["findings"]
                if isinstance(findings,list) and 1<=len(findings)<=8:
                    for f in findings:
                        statement,citations=f["statement"],f["evidence_ids"]
                        if (not isinstance(statement,str) or not 1<=len(statement)<=500 or UNSAFE.search(statement)
                                or ai_failover.BLOCKED.search(statement) or not isinstance(citations,list)
                                or not 1<=len(citations)<=5 or any(c not in pack for c in citations)):
                            raise ValueError("INVALID_FINDING")
                        clean.append({"statement":statement,"evidence_ids":citations})
        except Exception:
            clean=[]
        with closing(db_connect()) as db,db:
            db.execute("UPDATE portfolio_local_ai SET status=?,payload=? WHERE evidence_hash=? AND attempted_at=?",
                ("AVAILABLE" if clean else "UNAVAILABLE",json.dumps(clean) if clean else None,key,instant.isoformat()))
            db.execute("DELETE FROM portfolio_local_ai WHERE attempted_at<?",((instant-timedelta(days=7)).isoformat(),))
        return


def _items(snapshot):
    return [item for item,_ in company.identify(snapshot)]


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
        for row in db.execute("SELECT instrument_key FROM automatic_news_state").fetchall():
            if row["instrument_key"] not in active_keys:
                db.execute("DELETE FROM automatic_news_state WHERE instrument_key=?",(row["instrument_key"],))
    # Reuse the existing bounded adapters with an isolated private cache.
    company.refresh(snapshot,db_connect,instant=instant)
    news.refresh(snapshot,db_connect,instant=instant)
    company.attach(snapshot,db_connect,instant)
    news.attach(snapshot,db_connect,instant)
    _review(_items(snapshot),db_connect,runner,instant)


def read(rows,db_connect=connect,instant=None):
    if not enabled():
        return {"items":{},"status":"DISABLED"}
    instant=instant or datetime.now(timezone.utc)
    snapshot=selection(rows)
    company.attach(snapshot,db_connect,instant)
    news.attach(snapshot,db_connect,instant)
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
        if type(code) is not int or code in result or row.get("amfi_option")!="GROWTH":
            continue
        if not fund_disclosures._day(row.get("amfi_metadata_date"),today,7):
            continue
        matches=fund_disclosures.matched([row],today)
        if len(matches)!=1:
            continue
        disclosure=matches[0]
        portfolios=fund_portfolios.matched([disclosure],instant)
        result[str(code)]={"status":"SECONDARY_REPORTED_EVIDENCE",
            "disclosure":disclosure,"portfolio":portfolios[0] if len(portfolios)==1 else None,
            "notice":"Exact held scheme, secondary reported evidence only; official filings, benchmark history and forward growth remain unverified."}
    return result
