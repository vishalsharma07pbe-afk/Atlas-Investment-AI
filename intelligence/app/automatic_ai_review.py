"""Bounded public-evidence AI reviews; independent of browser and holdings.

Existing provider permissions and shared budget reservations remain authoritative.
No private portfolio inputs, arbitrary text, targets, or trade actions enter this path.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import json
import math
import os
import re
import sqlite3

from . import ai_failover, ai_public_evidence, ai_claims, company_reports

VERSION = "AUTO-GROUNDED-5"
BATCH_SIZE = 2
ROLES = ("TECHNICAL_EVIDENCE", "ADVERSARIAL_RISK", "FINANCIAL_EVIDENCE", "HISTORICAL_VALIDATION", "EVIDENCE_COMPLETENESS")
ROLE_TASKS = {
    "TECHNICAL_EVIDENCE": "Review dated price, volatility and technical observations; distinguish raw and adjusted evidence.",
    "ADVERSARIAL_RISK": "Challenge overinterpretation, missing evidence, headline topics and market-level risk limitations.",
    "FINANCIAL_EVIDENCE": "Review reported annual financial trends, quarterly ownership and peer multiples if supplied; explicitly identify valuation and business evidence gaps.",
    "HISTORICAL_VALIDATION": "Review supplied historical simulations, costs, drawdowns and small-sample limitations.",
    "EVIDENCE_COMPLETENESS": "Review missing evidence and inconsistencies across available domains, including separately dated global context and reported institutional flows; identify what cannot be established.",
}
HORIZONS = ("SWING", "SHORT_TERM", "LONG_TERM")
SYMBOL = re.compile(r"^[A-Z0-9._&-]{1,40}$")
UNSAFE = re.compile(r"\b(?:buy|sell|stop.loss|price target|guaranteed|guarantee|risk.free)\b", re.I)


def enabled():
    return os.getenv("ATLAS_AUTOMATIC_AI_REVIEW_ENABLED", "false").lower() == "true"


def providers():
    if not enabled():
        return []
    external = os.getenv("ATLAS_AUTOMATIC_EXTERNAL_AI_ALLOWED", "false").lower() == "true"
    order = ai_failover._order()
    # Local-first even if the manual router has a different preference.
    ordered = sorted(order, key=lambda p: p != "OLLAMA")
    return [p for p in ordered if (p == "OLLAMA" or external) and ai_failover._enabled(p)][:5]


def evidence(candidate, horizon, context=None):
    if horizon not in (*HORIZONS,"ELITE") or candidate.get("exchange") not in ("NSE", "BSE"):
        raise ValueError("INVALID_CANDIDATE")
    symbol = candidate.get("symbol")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("INVALID_SYMBOL")
    observed = date.fromisoformat(candidate["as_of"]).isoformat()
    numeric = {}
    for key in ("close", "history_count", "atr_percent", "momentum_20d_percent",
                "relative_volume_20", "rsi_14", "median_daily_traded_value"):
        value = candidate.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("INVALID_OBSERVATION")
        numeric[key] = value
    if not ({"close","history_count"} if horizon=="ELITE" else {"close","history_count","atr_percent"}) <= numeric.keys():
        raise ValueError("INCOMPLETE_OBSERVATIONS")
    adjustment = candidate.get("adjustment_status")
    if adjustment not in ("RAW_UNADJUSTED", "ADJUSTED"):
        raise ValueError("INVALID_ADJUSTMENT")
    pack = {"version": VERSION, "symbol": symbol, "exchange": candidate["exchange"],
            "as_of": observed, "horizon": horizon, "adjustment": adjustment,
            "observations": numeric,
            "missing": ["Live liquidity", "Independently verified current company fundamentals", "Dated intrinsic valuation",
                        "Stock-level institutional transactions", "Verified material news and impact", "Prospective strategy validation"]}
    # Only dated, allowlisted numeric summaries for the same public ISIN.
    # Never forward provider prose, URLs, notes, holdings or arbitrary fields.
    company=candidate.get("company_evidence") or {}
    isin=candidate.get("isin")
    if isinstance(isin,str) and re.fullmatch(r"IN[A-Z0-9]{10}",isin) and company.get("isin")==isin:
        trends=[]
        for row in (company.get("financial_trends") or {}).get("items",[])[:10]:
            if (row.get("metric") not in ("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW","TOTAL_ASSETS","TOTAL_LIABILITIES")
                or row.get("latest_period_may_be_stale") is not False
                or type(row.get("latest_year")) is not int or type(row.get("previous_year")) is not int
                or not 2000<=row["previous_year"]<row["latest_year"]<=date.fromisoformat(observed).year
                or row["latest_year"]-row["previous_year"]!=1
                or date.fromisoformat(observed).year-row["latest_year"]>1
                or row.get("direction") not in ("INCREASED","DECREASED","UNCHANGED")):
                continue
            change=row.get("change_percent")
            if change is not None and (type(change) not in (int,float) or not math.isfinite(change)):
                continue
            trends.append({"metric":row["metric"],"previous_year":row["previous_year"],"latest_year":row["latest_year"],
                           "direction":row["direction"],"change_percent":change})
        if trends:
            pack["financial_trends"]=sorted(trends,key=lambda r:r["metric"])
    replay=candidate.get("matched_strategy_replay") or {}
    if replay.get("as_of")==observed and replay.get("status")=="REPLAY_OBSERVED" and type(replay.get("trades")) is int and replay["trades"]>0:
        costs=[]
        for row in replay.get("cost_scenarios",[]):
            if row.get("cost_bps_per_side") not in (15,30,60):
                continue
            if all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in ("net_return_percent","max_drawdown_percent")):
                costs.append({k:row[k] for k in ("cost_bps_per_side","net_return_percent","max_drawdown_percent")})
        if costs:
            pack["historical_replay"]={"trades":replay["trades"],"cost_scenarios":costs,"small_sample":replay["trades"]<30}
    if context is not None:
        pack.update(ai_public_evidence.summarize(candidate, context, observed))
    return pack


def identity(pack, selected=None):
    # A changed permitted provider plan never silently reuses a completed committee.
    plan=list(selected or [])
    models={p:os.getenv("ATLAS_"+p+"_MODEL",ai_failover.DEFAULT_MODELS.get(p,"")) for p in plan}
    scope={"evidence":pack,"plan":plan,"models":models}
    return sha256(json.dumps(scope, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS automatic_ai_reviews(
        evidence_hash TEXT PRIMARY KEY, attempted_at TEXT NOT NULL,
        status TEXT NOT NULL, result TEXT NOT NULL)""")


def _read(connect, key):
    with closing(connect()) as db:
        _table(db)
        row = db.execute("SELECT attempted_at,status,result FROM automatic_ai_reviews WHERE evidence_hash=?", (key,)).fetchone()
        return (row[0], row[1], json.loads(row[2])) if row else None


def _claim(connect, key, now):
    with closing(connect()) as db, db:
        _table(db)
        db.execute("BEGIN IMMEDIATE")
        row=db.execute("SELECT attempted_at,status,result FROM automatic_ai_reviews WHERE evidence_hash=?",(key,)).fetchone()
        previous={}
        if row:
            status=row[1]
            if status=="COMPLETE":
                return None
            if status!="PENDING_MEMBERS" and row[0]>(now-timedelta(hours=6)).isoformat():
                return None
            previous=json.loads(row[2])
        db.execute("""INSERT INTO automatic_ai_reviews VALUES(?,?,'RUNNING',?)
            ON CONFLICT(evidence_hash) DO UPDATE SET attempted_at=excluded.attempted_at,
            status='RUNNING',result=excluded.result""",
            (key,now.isoformat(),json.dumps(previous,allow_nan=False)))
        return previous


def _finish(connect, key, claimed_at, status, result):
    with closing(connect()) as db, db:
        db.execute("""UPDATE automatic_ai_reviews SET status=?,result=?
            WHERE evidence_hash=? AND status='RUNNING' AND attempted_at=?""",
            (status,json.dumps(result,allow_nan=False),key,claimed_at.isoformat()))
        db.execute("DELETE FROM automatic_ai_reviews WHERE attempted_at<?",
                   ((datetime.now(timezone.utc)-timedelta(days=14)).isoformat(),))


def _review(pack, provider, runner, role="TECHNICAL_EVIDENCE"):
    # Text is entirely constructed from public, typed observations.
    supplied=_supplied(pack)
    prompt = ("Review this dated research watch for research purposes only. "
              "Assigned independent review role: "+ROLE_TASKS[role]+" "
              "Return 1 to 8 independent factual observations using the existing JSON findings schema. "
              "Each finding statement MUST itself be a JSON object encoded as a string, with exactly keys path and value. "
              'Example statement content: {"path":"/OBS/observations/atr_percent","value":2}. '
              "Use slash-separated paths through the supplied evidence JSON, zero-based array indexes, and the exact scalar value. "
              "Cite exactly the top-level evidence ID in evidence_ids. For missing evidence cite a specific LIMITS array entry. "
              "Choose important observations for your role. Do not add prose, invent paths or values, infer recommendations, "
              "predict outcomes, calculate new values or assert that another reviewer agrees. "
              "Each COMPANY listing observation has its own venue, date and horizon; do not transfer values across them. "
              "Ownership percentages are not transactions; flows are market-level. News topics are unverified. "
              "Peer multiples are undated, global changes are not synchronized, and replay is not forward performance. "
              "The system will validate each assertion against the supplied observations.\n"
              + json.dumps(supplied, ensure_ascii=True,separators=(",",":")))
    if pack.get("version")=="AUTO-FUND-GROUNDED-1":
        prompt=("Review the supplied public mutual fund's historical quarterly earnings exposure, not private holdings. "
                "Return one to eight findings using the existing findings schema. Each statement must be a JSON string "
                "with exactly keys path and value, for example {\"path\":\"/OBS/quarter\",\"value\":\"2026-09-30\"}. "
                "Cite exactly OBS or LIMITS as appropriate. Use exact scalar values only; do not extrapolate, predict NAV, "
                "infer recommendations, or treat original fund weight as company earnings growth. "
                "All statements are checked against the supplied evidence.\n"+json.dumps(supplied,ensure_ascii=True,separators=(",",":")))
    result = runner(prompt, list(supplied), providers=[provider])
    response = result.get("response")
    if result.get("status") != "MODEL_GROUNDED" or result.get("provider") != provider or not isinstance(response, dict):
        return None
    findings = response.get("findings")
    if not isinstance(findings, list) or not 1<=len(findings)<=8:
        return None
    # Free prose, unsupported paths and mismatched citations are never accepted.
    # Keep safe audit outcomes, not raw model statements or incorrect values.
    audit=ai_claims.audit(supplied,findings)
    if not audit["claims"]:
        return None
    return {"provider":provider,"role":role,"findings":audit["findings"],
            "claim_audit":{k:v for k,v in audit.items() if k!="findings"}}


def _company_candidates(snapshot,selected):
    # One exact company pack across all current eligible venues and horizons.
    # Duplicate category/overall Elite references share the same evidence hash.
    for isin,entries in sorted(company_reports.grouped(snapshot).items()):
        packs={}
        targets=[]
        conflict=False
        for horizon,item in entries:
            try:
                pack=evidence(item,horizon,snapshot)
            except (ValueError,KeyError,TypeError,OverflowError):continue
            key=(horizon,item["exchange"],item["id"],pack["as_of"])
            if key in packs and packs[key]!=pack:conflict=True
            packs[key]=pack
            targets.append(item)
        if conflict or not packs or len(packs)>20:continue
        ordered=[packs[k] for k in sorted(packs)]
        # Keep source-specific observations and news/replays explicitly scoped.
        # Shared company domains appear once, and conflicting values are omitted.
        root={**ordered[0],"version":"AUTO-COMPANY-GROUNDED-1","company_isin":isin}
        root.pop("historical_replay",None);root.pop("news_topics",None)
        root["listing_observations"]=[]
        for p in ordered:
            listing={k:p[k] for k in ("symbol","exchange","as_of","horizon","adjustment","observations")}
            for k in ("historical_replay","benchmark_regime","market_flows"):
                if k in p:listing[k]=p[k]
            root["listing_observations"].append(listing)
        for k in ("financial_trends","ownership_context","peer_valuation","news_topics","global_changes","benchmark_regime","market_flows"):
            root.pop(k,None)
            available=[p[k] for p in ordered if k in p]
            if available and all(v==available[0] for v in available):
                root[k]=available[0]
            elif available:
                root["missing"]=[*root["missing"],"Conflicting shared "+k+" observations"]
        key=identity(root,selected)
        for item in targets:yield item,root,key

def candidates(snapshot, selected=None):
    if snapshot.get("scope")=="PUBLIC_MARKET_RESEARCH_ONLY":
        yield from _company_candidates(snapshot,selected)
        return
    for section in snapshot["sections"]:
        if section["section"] not in ("NSE", "BSE") or section["status"]!="READY":
            continue
        for horizon in HORIZONS:
            for item in (section.get("result") or {}).get("horizons", {}).get(horizon, {}).get("candidates", []):
                try:
                    pack = evidence(item, horizon, snapshot if snapshot.get("scope")=="PUBLIC_MARKET_RESEARCH_ONLY" else None)
                    yield item, pack, identity(pack,selected)
                except (ValueError, KeyError, TypeError, OverflowError):
                    continue


def _committee(pack, selected, reviews, attempted):
    indexed={r["provider"]:r for r in reviews if r.get("provider") in selected}
    expected=list(_supplied(pack))
    cited={c for r in indexed.values() for f in r["findings"] for c in f["evidence_ids"]}
    members=[{"provider":p,"role":ROLES[i],"status":"REVIEW_RETURNED" if p in indexed else
              "NO_USABLE_REVIEW" if p in attempted else "PENDING",
              "cited_domains":sorted({c for f in indexed[p]["findings"] for c in f["evidence_ids"]}) if p in indexed else []}
             for i,p in enumerate(selected)]
    comparison=ai_claims.compare(supplied=_supplied(pack),reviews=list(indexed.values()))
    return {"status":"ALL_CONFIGURED_REVIEWS_RETURNED" if len(indexed)==len(selected) and selected else
            "PARTIAL_REVIEWS" if indexed else "AWAITING_REVIEWS",
            "configured_count":len(selected),"reviewed_count":len(indexed),"members":members,
            "available_domains":expected,"cited_domains":[k for k in expected if k in cited],
            "uncited_domains":[k for k in expected if k not in cited],
            "agreement_status":comparison["status"],"claim_comparison":comparison,
            "notice":"Exact scalar checks against the supplied evidence only, not independent source verification, interpretive agreement, confidence or investment qualification."}


def refresh(snapshot, connect, runner=ai_failover.grounded_research, *, candidate_loader=None):
    if not snapshot["enabled"] or not enabled():
        return
    selected=providers()
    if not selected:
        return
    now=datetime.now(timezone.utc)
    # Up to two calls per pass, one evidence pack; up to five permitted
    # providers across passes. Keep valid reviews while retrying missing roles.
    seen=set()
    for _,pack,key in (candidate_loader or candidates)(snapshot,selected):
        if key in seen:continue
        seen.add(key)
        previous=_claim(connect,key,now)
        if previous is None:
            continue
        reviews=[r for r in previous.get("reviews",[]) if r["provider"] in selected]
        completed={r["provider"] for r in reviews}
        attempted=set(previous.get("attempted_providers",[]))&set(selected)
        if set(selected)<=attempted:
            attempted=set(completed)
        pending=[p for p in selected if p not in attempted and p not in completed]
        for provider in pending[:BATCH_SIZE]:
            attempted.add(provider)
            try:
                review=_review(pack,provider,runner,ROLES[selected.index(provider)])
                if review is not None:
                    reviews.append({**review,"reviewed_at":now.isoformat()})
            except Exception:
                # Do not store raw provider errors or let a model block research.
                continue
        completed={r["provider"] for r in reviews}
        result={"reviews":reviews,"evidence":pack,"reviewed_at":now.isoformat(),
                **({"company_isin":pack["company_isin"]} if "company_isin" in pack else {}),
                "attempted_providers":[p for p in selected if p in attempted],
                "notice":"Accepted findings are deterministic restatements of matching supplied observations. Incorrect or unsupported assertions are withheld; source truth and investment suitability are not established.",
                "committee":_committee(pack,selected,reviews,attempted)}
        status=("COMPLETE" if len(completed)==len(selected) else
                "PENDING_MEMBERS" if any(p not in attempted for p in selected) else
                "PARTIAL" if reviews else "UNAVAILABLE")
        _finish(connect,key,now,status,result)
        return


def attach(snapshot, connect):
    # Always clear previously attached reviews, even if permission or evidence changes.
    for section in snapshot.get("sections",[]):
        for group in ((section.get("result") or {}).get("horizons") or {}).values():
            if isinstance(group,dict):
                for item in group.get("candidates",[]):
                    if isinstance(item,dict):
                        item.pop("ai_review",None)
    for _,item in company_reports.entries(snapshot):
        item.pop("ai_review",None)
    # Only display reviews for the exact current evidence, model and permitted plan.
    if not snapshot["enabled"] or not enabled():
        snapshot["automatic_ai_status"]="DISABLED"
        return snapshot
    allowed=providers()
    snapshot["automatic_ai_status"]="ENABLED" if allowed else "NO_CONFIGURED_PROVIDER"
    if not allowed:
        return snapshot
    cached={}
    for item,pack,key in candidates(snapshot,allowed):
        item.pop("ai_review",None)
        if key not in cached:cached[key]=_read(connect,key)
        row=cached[key]
        if not row or row[1] not in ("COMPLETE","PARTIAL","PENDING_MEMBERS","RUNNING"):
            continue
        result=row[2]
        reviews=[r for r in result.get("reviews",[]) if r["provider"] in allowed]
        if reviews:
            item["ai_review"]={**result,"reviews":reviews,
                "committee":_committee(pack,allowed,reviews,set(result.get("attempted_providers",[])))}
    return snapshot


def _supplied(pack):
    if pack.get("version")=="AUTO-FUND-GROUNDED-1":
        return {"OBS":pack["fund"],"LIMITS":pack["missing"]}
    domains={"financial_trends":"FUND","historical_replay":"REPLAY",**ai_public_evidence.DOMAINS}
    # OBS remains an explicit field allowlist, never an arbitrary remainder.
    supplied={"OBS":{k:pack[k] for k in ("version","symbol","exchange","as_of","horizon","adjustment","observations")},"LIMITS":pack["missing"]}
    for key,identifier in domains.items():
        if key in pack:
            supplied[identifier]=pack[key]
    if "company_isin" in pack:
        supplied["COMPANY"]={"isin":pack["company_isin"],"listing_observations":pack["listing_observations"]}
    return supplied
