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

def temporal_diagnostics(selected,horizon,today,truncated):
    """Fixed disjoint publication quarters, not fitted or independent trials.

    Group by publication date first, then weight each date equally. Retain
    missing selected outcomes, including dates with no observed result.
    """
    from . import research_reliability as rel
    groups=defaultdict(list)
    for r in selected:
        day=r[1]
        groups[(day.year,(day.month-1)//3+1,r[2]["score_band"])].append(r)
    result=[];day_values={}
    for (year,quarter,label),items in sorted(groups.items()):
        # Only assess completed publication quarters whose last possible
        # publication has passed the full predeclared maturity allowance.
        month=quarter*3
        from calendar import monthrange
        end=date(year,month,monthrange(year,month)[1])
        if today<=end+timedelta(days=rel.HORIZONS[horizon]+7):continue
        by_day=defaultdict(list)
        for r in items:by_day[r[1]].append(r)
        observed=[r for r in items if r[3] is not None]
        complete_dates=0;date_means=[];daily={}
        for day,rows in sorted(by_day.items()):
            returns=[(1+r[3])*(1-.003)**2-1 for r in rows if r[3] is not None]
            # Require 80% outcome coverage on a date, not simply a surviving winner.
            if len(returns)/len(rows)>=.8:
                daily[day]=mean(returns)*100;date_means.append(daily[day]);complete_dates+=1
        coverage=len(observed)/len(items)
        dates_coverage=complete_dates/len(by_day)
        enough=(not truncated and len(observed)>=30 and len({r[0] for r in observed})>=10 and
                coverage>=.8 and complete_dates>=10 and dates_coverage>=.8)
        if enough:day_values[(f"{year}-Q{quarter}",label)]=daily
        result.append({"publication_quarter":f"{year}-Q{quarter}","score_band":label,
            "mature_count":len(items),"observed_count":len(observed),"distinct_isins":len({r[0] for r in observed}),
            "publication_dates":len(by_day),"covered_dates":complete_dates,"coverage_percent":round(100*coverage,2),
            "date_coverage_percent":round(100*dates_coverage,2),
            "equal_date_mean_net_change_percent":round(mean(date_means),4) if enough else None,
            "positive_date_count":sum(x>0 for x in date_means) if enough else None,
            "status":"DESCRIPTIVE_QUARTER_ONLY" if enough else "INSUFFICIENT_EVIDENCE"})
    # Compare fixed top vs bottom bands only in common quarters where both
    # independently meet the descriptive evidence gate. Never pick cutoffs.
    contrasts=[]
    for quarter in sorted({r["publication_quarter"] for r in result}):
        bands={r["score_band"]:r for r in result if r["publication_quarter"]==quarter}
        low,high=bands.get(SCORE_BANDS[0]),bands.get(SCORE_BANDS[-1])
        if low and high and low["status"]==high["status"]=="DESCRIPTIVE_QUARTER_ONLY":
            a=day_values[(quarter,SCORE_BANDS[0])];b=day_values[(quarter,SCORE_BANDS[-1])]
            matched=sorted(a.keys()&b.keys())
            if len(matched)<10 or len(matched)/max(len(a),len(b))<.8:continue
            contrasts.append({"publication_quarter":quarter,"matched_publication_dates":len(matched),
                "high_minus_low_pp":round(mean(b[d]-a[d] for d in matched),4)})
    return {"status":"DESCRIPTIVE_TEMPORAL_COMPARISON" if len(contrasts)>=2 and not truncated else "AWAITING_COMPARABLE_QUARTERS",
        "quarter_bands":result,"comparable_quarters":contrasts,
        "positive_spread_quarters":sum(r["high_minus_low_pp"]>0 for r in contrasts),
        "calibrated":False,
        "notice":"Fixed mature calendar publication quarters; 30 bps/side; equal weight per covered publication date. "
                 "High-minus-low uses only common covered dates. No independence, statistical significance, model fit or confidence."}

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
        "temporal_diagnostics":temporal_diagnostics(selected,horizon,today,truncated),
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
