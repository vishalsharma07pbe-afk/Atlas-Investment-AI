"""Observed benchmark regime and separately dated context; no trading qualification."""
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from math import isfinite,log,sqrt
from statistics import pstdev
from zoneinfo import ZoneInfo
import json

from .market_client import backend_json
from .replay_evidence import session_audit
from .strategy_validation import REGIME_LOOKBACK,REGIME_THRESHOLD
from . import regime_features, relative_strength

IST=ZoneInfo("Asia/Kolkata")
HIGH_VOL=regime_features.HIGH_VOL
MIN_BREADTH=30
NOTICE=("Nifty 50 price-index trend uses the existing 60-session +/-5% replay thresholds; 20-session annualized historical volatility "
        "at least 25% is a descriptive high-volatility flag, not a calibrated risk boundary. Latest prior regular sessions match the stored calendar only. "
        "Breadth is from a bounded current registry sample of adjusted histories, not the exchange or index constituents. "
        "Daily breadth and 60-session trend have different horizons; disagreement is a research prompt. Institutional and global data are separate context, "
        "not causal attribution or synchronized evidence. No market prediction, strategy suitability validation or ranking change.")

def empty(status):
    return {"status":status,"trend":"UNAVAILABLE","notice":NOTICE}

def analyze(benchmark,calendar,today):
    result=empty("BENCHMARK_EVIDENCE_UNAVAILABLE")
    try:
        if benchmark.get("benchmark_key")!="NSE_INDEX|Nifty 50" or benchmark.get("kind")!="PRICE_INDEX":
            return result
        rows=benchmark["candles"]
        if not isinstance(rows,list) or not 61<=len(rows)<=400:
            return result
        indexed={}
        for row in rows:
            day=date.fromisoformat(row["trade_date"])
            close=float(row["close"])
            if (day>=today or day in indexed or row.get("source_code")!="UPSTOX" or type(row.get("revision")) is not int
                    or row["revision"]<1 or not isfinite(close) or not 0<close<=1e9):
                return result
            indexed[day]=close
        dates=sorted(indexed)[-(REGIME_LOOKBACK+1):]
        if not 1<=(today-dates[-1]).days<=7:
            return result
        audit=session_audit({"first_date":dates[0].isoformat(),"observations":[d.isoformat() for d in dates]},calendar,"NSE",today)
        if audit["status"]!="STORED_SESSIONS_MATCHED":
            return empty(audit["status"])
        features=regime_features.describe([d.isoformat() for d in dates],[indexed[d] for d in dates])
        if features is None:
            return result
        return {"status":"OBSERVED_BENCHMARK_REGIME",**features,
                "as_of":dates[-1].isoformat(),"previous_session":dates[-2].isoformat(),"first_session":dates[0].isoformat(),
                "relative_strength_windows":relative_strength.benchmark_windows(indexed,calendar,today),
                "calendar_checked_on":today.isoformat(),"last_five_sessions":[d.isoformat() for d in reversed(dates[-5:])],"notice":NOTICE}
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,ZeroDivisionError):
        return result

def _table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS market_regime_snapshot(
        id INTEGER PRIMARY KEY CHECK(id=1),captured_at TEXT NOT NULL,payload TEXT NOT NULL)""")

def refresh(connect,loader=backend_json,instant=None):
    instant=instant or datetime.now(timezone.utc)
    today=instant.astimezone(IST).date()
    report=analyze(loader("/api/v1/market-data/strategy-benchmark"),loader("/api/v1/market-data/strategy-calendar?exchange=NSE"),today)
    with closing(connect()) as db,db:
        _table(db)
        db.execute("""INSERT INTO market_regime_snapshot VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET captured_at=excluded.captured_at,payload=excluded.payload
            WHERE excluded.captured_at>=market_regime_snapshot.captured_at""",
            (instant.isoformat(),json.dumps(report,allow_nan=False)))
    return report["status"]=="OBSERVED_BENCHMARK_REGIME"

def read(connect,instant):
    with closing(connect()) as db:
        _table(db)
        row=db.execute("SELECT captured_at,payload FROM market_regime_snapshot WHERE id=1").fetchone()
    if not row:
        return empty("AWAITING_BENCHMARK")
    stamp=datetime.fromisoformat(row["captured_at"])
    if stamp.tzinfo is None or not timedelta(0)<=instant-stamp<=timedelta(hours=2) or stamp.astimezone(IST).date()!=instant.astimezone(IST).date():
        return empty("STALE_CAPTURE")
    return json.loads(row["payload"])

def _breadth(snapshot,report,today):
    result={"status":"UNAVAILABLE"}
    sections=[s for s in snapshot.get("sections",[]) if s.get("section")=="NSE" and s.get("status")=="READY"]
    if len(sections)!=1:
        return result
    data=sections[0].get("result") or {}
    coverage=data.get("discovery_coverage") or {}
    b=data.get("sample_breadth") or {}
    if (coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("expected_session")!=report["as_of"]
            or b.get("as_of")!=report["as_of"] or b.get("adjustment_status")!="ADJUSTED"):
        return result
    pairs=[p for p in b.get("pairs",[]) if p.get("previous_session")==report["previous_session"]]
    if len(pairs)!=1:
        return result
    fields=("advancing","declining","unchanged")
    values=[pairs[0].get(k) for k in fields]
    selected=coverage.get("selected_count")
    if any(type(v) is not int or v<0 for v in values) or type(selected) is not int or not 1<=selected<=20000:
        return result
    total=sum(values)
    if not 0<total<=selected:
        return result
    result.update(**dict(zip(fields,values)),matched_count=total,selected_count=selected)
    if total<MIN_BREADTH or total*2<selected:
        result["status"]="INSUFFICIENT_SAMPLE_COVERAGE"
        return result
    result["status"]="MATCHED_SAMPLE_ONLY"
    result["direction"]="ADVANCING_MAJORITY" if values[0]*2>total else "DECLINING_MAJORITY" if values[1]*2>total else "MIXED"
    return result

def _institutional(snapshot,report):
    result={"status":"UNAVAILABLE"}
    source=snapshot.get("institutional_activity") or {}
    if source.get("status")!="RECENT_PROVIDER_EVIDENCE":
        return result
    windows=(source.get("session_flow_context") or {}).get("windows",[])
    found=[w for w in windows if w.get("session_count")==5 and w.get("status")=="STORED_REGULAR_SESSIONS_MATCHED"]
    if len(found)!=1:
        return result
    metrics=found[0].get("metrics") or {}
    if metrics.get("dates")!=report["last_five_sessions"]:
        return result
    participants=metrics.get("participants") or {}
    fii=(participants.get("FII") or {}).get("direction_consistency")
    dii=(participants.get("DII") or {}).get("direction_consistency")
    allowed=("NET_BUYING_MAJORITY","NET_SELLING_MAJORITY","MIXED_OR_BALANCED")
    if fii in allowed and dii in allowed:
        result.update(status="MATCHED_REPORTED_SESSIONS",fii=fii,dii=dii)
    return result

def attach(snapshot,connect,instant):
    report=read(connect,instant) if snapshot.get("enabled") else empty("DISABLED")
    snapshot["market_regime"]=report
    if not snapshot.get("enabled"):
        return snapshot
    context=snapshot.get("global_context") or {}
    report["global_coverage"]={"available_count":context.get("available_count",0),"total_count":context.get("total_count",0)}
    if report["status"]!="OBSERVED_BENCHMARK_REGIME":
        return snapshot
    report["breadth"]=_breadth(snapshot,report,instant.astimezone(IST).date())
    report["institutional"]=_institutional(snapshot,report)
    _attach_strategy_context(snapshot,report)
    direction=report["breadth"].get("direction")
    trend=report["trend"]
    report["agreement"]="UNAVAILABLE" if direction is None else "MIXED_OR_DIFFERENT_HORIZONS"
    if (trend,direction) in (("RISING","ADVANCING_MAJORITY"),("FALLING","DECLINING_MAJORITY")):
        report["agreement"]="SAME_DIRECTION_OBSERVATION"
    elif (trend,direction) in (("RISING","DECLINING_MAJORITY"),("FALLING","ADVANCING_MAJORITY")):
        report["agreement"]="OPPOSING_DAILY_BREADTH_REVIEW"
    return snapshot


def _attach_strategy_context(snapshot,report):
    """Use only already identity/provenance-matched replay for the same stock."""
    from .automatic_company_evidence import identify
    for item,_ in identify(snapshot):
        if item.get("exchange")!="NSE" or item.get("as_of")!=report.get("as_of"):
            continue
        replay=item.get("matched_strategy_replay") or {}
        if replay.get("status")!="REPLAY_OBSERVED" or replay.get("as_of")!=report["as_of"]:
            continue
        research=replay.get("joint_regime_research") or {}
        latest=research.get("latest_benchmark_context") or {}
        if (research.get("methodology")!=regime_features.VERSION or latest.get("as_of")!=report["as_of"]
                or not report.get("benchmark_fingerprint") or latest.get("benchmark_fingerprint")!=report["benchmark_fingerprint"]
                or latest.get("trend")!=report.get("trend") or latest.get("volatility_regime")!=report.get("volatility_regime")):
            continue
        groups=[g for g in research.get("groups",[]) if g.get("trend")==report["trend"]
                and g.get("volatility_regime")==report["volatility_regime"]]
        if len(groups)!=1:
            continue
        group=groups[0]
        count=group.get("trades")
        if type(count) is not int or count<0:
            continue
        item["current_regime_replay"]={"status":"NO_MATCHED_POSITIONS" if count==0 else "SMALL_HISTORICAL_SAMPLE" if count<30 else "DESCRIPTIVE_HISTORICAL_COHORT",
            "as_of":report["as_of"],"trend":report["trend"],"volatility_regime":report["volatility_regime"],
            "trades":count,"cost_scenarios":group.get("cost_scenarios",[]) if count else [],
            "notice":"Same-stock historical positions in the matching signal-date trend and volatility category. Exact current benchmark fingerprint matched; outcomes do not validate future suitability or change qualification."}
