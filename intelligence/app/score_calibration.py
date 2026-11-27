"""Prospective diagnostics for frozen technical score and historical price-risk bands.

No retrospective reconstruction, fitting, probability, score/ranking changes
or investment qualification. Public watch publications only.
"""
from collections import defaultdict
from contextlib import closing
from datetime import date,datetime,timedelta,timezone
from math import isfinite
from statistics import mean,median
from zoneinfo import ZoneInfo
import json
import re
from .horizon_research import VERSION as TECH_VERSION
from .replay_evidence import exact_isin

VERSION="FROZEN-TECHNICAL-SCORE-1"
IST=ZoneInfo("Asia/Kolkata")
WINDOW={"SWING":20,"SHORT_TERM":60,"LONG_TERM":120}
SCORE_BANDS=("BELOW_5","5_TO_BELOW_15","15_OR_ABOVE")
RISK_BANDS=("LOW","MEDIUM","HIGH","UNAVAILABLE")
NOTICE=("Original technical rule scores only, measured on subsequent observed close marks of public watches. "
        "Fixed illustrative bands, not fitted cutoffs, confidence percentages, expected returns or suitability. "
        "Non-overlapping company windows selected before outcomes or score availability are considered. "
        "Missing mature outcomes stay in denominators. Same-horizon comparisons only; dependence across companies and dates remains. "
        "Cost assumptions are illustrative, not executable costs. No qualification or ranking change.")

def num(v,lo,hi):return type(v) in (int,float) and isfinite(v) and lo<=v<=hi

def band(score):return SCORE_BANDS[0] if score<5 else SCORE_BANDS[1] if score<15 else SCORE_BANDS[2]

def risk_band(dd,vol):return "HIGH" if dd>=20 or vol>=40 else "MEDIUM" if dd>=10 or vol>=25 else "LOW"

def capture(item,horizon,group,coverage,today):
    if horizon not in WINDOW or group.get("methodology")!=TECH_VERSION or group.get("status")!="TECHNICAL_WATCH_ONLY":return None
    if item.get("adjustment_status")!="ADJUSTED" or not exact_isin(item.get("isin")) or item.get("exchange") not in ("NSE","BSE"):return None
    if coverage.get("calendar_status")!="PUBLISHED_SESSION" or coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("expected_session")!=item.get("as_of"):return None
    try:
        if not 1<=(today-date.fromisoformat(item["as_of"])).days<=4:return None
        score=item["rank_score"];terms=item["rank_components"];window=item["score_window"]
        keys={"momentum_percent","atr_penalty"}|({"relative_volume_bonus"} if horizon=="SWING" else set())
        if not isinstance(terms,dict) or set(terms)!=keys or not all(num(v,-1e9,1e9) for v in terms.values()) or not num(score,-1e9,1e9):return None
        if abs(sum(terms.values())-score)>.0001 or terms["momentum_percent"]<=0 or not -(5 if horizon=="SWING" else 4)<=terms["atr_penalty"]<0:return None
        if horizon=="SWING" and not 2.4<=terms["relative_volume_bonus"]<=6:return None
        if window.get("last_date")!=item["as_of"] or not re.fullmatch(r"[a-f0-9]{64}",window["dates_digest"]) or not re.fullmatch(r"[A-Z0-9_-]{1,40}",window["source_code"]):return None
        if date.fromisoformat(window["first_date"])>=date.fromisoformat(item["as_of"]):return None
        if not num(window["return_percent"],-100,1e9) or abs(window["return_percent"]-terms["momentum_percent"])>.00001:return None
        risk=item.get("score_risk_path") or {}
        dd,vol=risk.get("maximum_close_drawdown_percent"),risk.get("annualized_daily_volatility_percent")
        historical={"band":"UNAVAILABLE"}
        if risk.get("first_date")==window["first_date"] and risk.get("last_date")==window["last_date"] and risk.get("adjustment_status")=="ADJUSTED" and num(dd,0,100) and num(vol,0,10000):
            historical={"band":risk_band(dd,vol),"drawdown_percent":dd,"annualized_volatility_percent":vol}
        return {"methodology":VERSION,"horizon":horizon,"score":score,"score_band":band(score),"components":dict(terms),
            "window_returns":WINDOW[horizon],"first_date":window["first_date"],"as_of":window["last_date"],
            "dates_digest":window["dates_digest"],"source_code":window["source_code"],"historical_risk":historical,
            "probability":None,"notice":NOTICE}
    except (ValueError,TypeError,KeyError,OverflowError):return None

def _frozen(evidence,horizon,observed):
    frozen=evidence.get("score_calibration")
    if not isinstance(frozen,dict) or frozen.get("methodology")!=VERSION or frozen.get("horizon")!=horizon or frozen.get("as_of")!=observed.isoformat() or frozen.get("window_returns")!=WINDOW[horizon]:return None
    score=frozen.get("score")
    if not num(score,-1e9,1e9) or frozen.get("score_band")!=band(score):return None
    risk=frozen.get("historical_risk") or {}
    b=risk.get("band")
    if b not in RISK_BANDS:return None
    if b!="UNAVAILABLE":
        dd,vol=risk.get("drawdown_percent"),risk.get("annualized_volatility_percent")
        if not num(dd,0,100) or not num(vol,0,10000) or risk_band(dd,vol)!=b:return None
    return frozen

def summarize(rows,horizon,today,truncated=False):
    from . import research_reliability as rel
    selected=[];last={};legacy=overlap=immature=invalid=0
    # Chronology independent of score and realized outcome, deterministic
    # tie break from query ordering; do not select later overlapping winners.
    for row in rows:
        try:
            evidence=json.loads(row["evidence"])
            published=rel._stamp(row["published_at"]);observed=date.fromisoformat(row["observed_date"]);maturity=date.fromisoformat(row["maturity_date"])
            isin=evidence.get("isin")
            if (not exact_isin(isin) or evidence.get("methodology")!=TECH_VERSION or evidence.get("adjustment_status")!="ADJUSTED"
                or not 0<=(published-observed).days<=4 or maturity!=published+timedelta(days=rel.HORIZONS[horizon])
                or not today-timedelta(days=rel.COHORT_DAYS)<=published<=today):
                invalid+=1;continue
            if today<=maturity+timedelta(days=7):
                immature+=1;continue
            if isin in last and published<=last[isin]:
                overlap+=1;continue
            last[isin]=maturity+timedelta(days=7)
            frozen=_frozen(evidence,horizon,observed)
            if frozen is None:
                legacy+=1;continue
            try:change=rel._outcome(row,published,maturity,today)
            except (ValueError,TypeError,KeyError,OverflowError):change=None
            selected.append((isin,published,frozen,change,rel._path_metrics(row,change)))
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            invalid+=1
    def describe(label,items):
        returns=[r[3] for r in items if r[3] is not None]
        observed=[r for r in items if r[3] is not None]
        paths=[r[4] for r in items if r[4] is not None]
        count=len(items);coverage=len(returns)/count if count else 0
        identities=len({r[0] for r in observed});dates=len({r[1] for r in observed})
        sufficient=not truncated and len(returns)>=30 and identities>=10 and dates>=10 and coverage>=.8
        return {"band":label,"status":"DESCRIPTIVE_SAMPLE_AVAILABLE" if sufficient else "INSUFFICIENT_EVIDENCE",
            "mature_count":count,"observed_count":len(returns),"distinct_isins":identities,"publication_dates":dates,
            "coverage_percent":round(coverage*100,2),"observed_paths":len(paths),
            "path_coverage_percent":round(100*len(paths)/count,2) if count else 0,
            "median_close_drawdown_percent":round(median(p[2] for p in paths),4) if paths else None,
            "worst_close_drawdown_percent":min(p[2] for p in paths) if paths else None,
            "cost_scenarios":[{"cost_bps_per_side":bps,"mean_net_change_percent":round(mean(net)*100,4),
                "median_net_change_percent":round(median(net)*100,4),"positive_count":sum(v>0 for v in net)}
                for bps in rel.COSTS if (net:=[(1+r)*(1-bps/10000)**2-1 for r in returns])]}
    scored=[describe(k,[r for r in selected if r[2]["score_band"]==k]) for k in SCORE_BANDS]
    risks=[describe(k,[r for r in selected if r[2]["historical_risk"]["band"]==k]) for k in RISK_BANDS]
    return {"methodology":VERSION,"horizon":horizon,"status":"DESCRIPTIVE_BAND_EVIDENCE" if any(b["status"]=="DESCRIPTIVE_SAMPLE_AVAILABLE" for b in scored) and not truncated else "AWAITING_CALIBRATION_EVIDENCE",
        "selected_scored_mature":len(selected),"legacy_or_unscored_mature":legacy,"overlap_excluded":overlap,"immature_excluded":immature,
        "invalid_excluded":invalid,"truncated":truncated,"score_bands":scored,"risk_bands":risks,
        "calibrated":False,"probability":None,"notice":NOTICE}

def read(connect,instant):
    from . import research_reliability as rel
    today=instant.astimezone(IST).date()
    with closing(connect()) as db:
        rel._table(db);out={}
        for h in WINDOW:
            rows=db.execute("""SELECT * FROM watch_outcomes WHERE horizon=? AND published_at>=?
              ORDER BY published_at,instrument_id,observed_date LIMIT ?""",(h,(instant-timedelta(days=rel.COHORT_DAYS+1)).isoformat(),rel.MAX_ROWS+1)).fetchall()
            out[h]=summarize(rows[:rel.MAX_ROWS],h,today,len(rows)>rel.MAX_ROWS)
    return {"methodology":VERSION,"horizons":out,"calibrated":False,"notice":NOTICE}

def attach(snapshot,connect,instant):
    if not snapshot.get("enabled"):return snapshot
    snapshot["score_calibration"]=read(connect,instant)
    today=instant.astimezone(IST).date()
    for section in snapshot.get("sections",[]):
        if section.get("status")!="READY" or section.get("section") not in ("NSE","BSE"):continue
        result=section.get("result") or {}
        for h in WINDOW:
            group=(result.get("horizons") or {}).get(h) or {}
            for row in group.get("candidates",[]):
                row.pop("score_evidence",None)
                if row.get("exchange")!=section["section"]:continue
                frozen=capture(row,h,group,result.get("discovery_coverage") or {},today)
                if frozen:row["score_evidence"]=frozen
    return snapshot
