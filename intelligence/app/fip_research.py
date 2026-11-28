"""FIP-inspired, fixed-rule public price research, separate from investment qualification."""
from collections import Counter,defaultdict
from contextlib import closing
from datetime import date,datetime,timedelta
from math import isfinite
from statistics import mean,median,stdev
from zoneinfo import ZoneInfo
import json
import re

from .replay_evidence import exact_isin,full_manifest,fingerprint
from . import company_venues

VERSION="FIP-MULTIWINDOW-1"
WINDOWS=(20,60,120,252)
HORIZON="FIP"
DAYS=60
IST=ZoneInfo("Asia/Kolkata")
NOTICE=("FIP-inspired fixed-rule price research, not the original published portfolio strategy. "
        "All four windows must have positive cumulative price return and negative information discreteness; "
        "60-return smoothness and historical turnover thresholds are provisional. "
        "Rank by equal-weight signed information discreteness, not future return or confidence. "
        "Provider-validated adjusted prices and locally stored regular sessions, not independent adjustment, "
        "calendar, point-in-time membership or execution verification. Current local sample only.")

def calendar_suffix(calendar,exchange,today):
    """Exact last 253 known regular sessions through yesterday; no skipped unknown days."""
    if not isinstance(calendar,dict) or calendar.get("exchange")!=exchange or calendar.get("through")!=(today-timedelta(days=1)).isoformat():return ()
    rows=calendar.get("days")
    if not isinstance(rows,list) or len(rows)>1100:return ()
    states={}
    try:
        for row in rows:
            d=date.fromisoformat(row["trade_date"]);state=row["state"]
            if d in states or not today-timedelta(days=1100)<=d<today or state not in ("REGULAR","CLOSED","UNKNOWN","SPECIAL_SESSION_UNSUPPORTED"):return ()
            states[d]=state
        days=[]
        for n in range(1,1101):
            d=today-timedelta(days=n)
            state=states.get(d)
            if state=="REGULAR":days.append(d.isoformat())
            elif state!="CLOSED":return ()
            if len(days)==253:return tuple(reversed(days))
    except (ValueError,TypeError,KeyError):pass
    return ()

def metrics(prices,volumes):
    if len(prices)!=253 or len(volumes)!=253 or any(not isfinite(p) or p<=0 for p in prices):return None
    returns=[b/a-1 for a,b in zip(prices,prices[1:])]
    if any(not isfinite(v) for v in returns):return None
    windows={}
    for n in WINDOWS:
        r=returns[-n:];change=prices[-1]/prices[-n-1]-1
        up=sum(v>0 for v in r);down=sum(v<0 for v in r)
        positive=sum(max(v,0) for v in r)
        ident=(down-up)/n*(1 if change>0 else -1) if change else None
        peak=prices[-n-1];dd=0.
        for p in prices[-n-1:]:
            peak=max(peak,p);dd=min(dd,p/peak-1)
        values=(change,dd,stdev(r)*(252**.5),positive)
        if not all(isfinite(v) for v in values):return None
        windows[str(n)]={"return_percent":round(change*100,6),"information_discreteness":round(ident,8) if ident is not None else None,
            "positive_days":up,"negative_days":down,"flat_days":n-up-down,
            "largest_gain_share_percent":round(max(r)/positive*100,6) if positive else None,
            "drawdown_percent":round(-dd*100,6),"annualized_volatility_percent":round(values[2]*100,6)}
    turnover=median(p*v for p,v in zip(prices[-20:],volumes[-20:]))
    if not isfinite(turnover):return None
    w=windows["60"];reasons=[]
    if any(v["return_percent"]<=0 or v["information_discreteness"] is None or v["information_discreteness"]>=0 for v in windows.values()):reasons.append("MULTIWINDOW_GRADUAL_POSITIVE_MOMENTUM_REQUIRED")
    if not 5<=w["return_percent"]<=50 or w["positive_days"]<33 or w["largest_gain_share_percent"] is None or w["largest_gain_share_percent"]>18 or max(returns[-60:])>=.10 or min(returns[-60:])<=-.12:reasons.append("SIXTY_RETURN_SMOOTHNESS_FILTER")
    if turnover<50_000_000 or volumes[-1]<=0:reasons.append("HISTORICAL_TURNOVER_FILTER")
    score=round(50*(1-mean(v["information_discreteness"] for v in windows.values())),6) if not reasons else None
    return {"methodology":VERSION,"status":"FIP_PRICE_MATCH" if not reasons else "FIP_FILTER_NOT_MET","score":score,
        "windows":windows,"median_daily_turnover_cr":round(turnover/1e7,4),"exclusions":reasons}

def observe(raw,calendar_dates,today):
    if len(calendar_dates)!=253 or len(raw)<253:return None
    sample=raw[-253:]
    audit=full_manifest(sample,today)
    if not audit or tuple(audit["observations"])!=calendar_dates:return None
    try:
        report=metrics([float(r["close"]) for r in sample],[int(r["volume"]) for r in sample])
        if report is None:return None
        return {**report,"first_date":calendar_dates[0],"as_of":calendar_dates[-1],"source_code":sample[-1]["source_code"],
            "history_fingerprint":audit["digest"],"replay_evidence_hash":fingerprint(sample,today),"calendar_status":"STORED_SESSIONS_MATCHED","adjustment_status":"ADJUSTED"}
    except (ValueError,TypeError,KeyError,OverflowError):return None

def replay(raw,today):
    """Called only AFTER existing full-history action, identity and calendar audit."""
    audit=full_manifest(raw,today)
    if not audit:return None
    rows=[r for r in raw if date.fromisoformat(r["trade_date"])<today]
    if len(rows)<274:return {"status":"INSUFFICIENT_REPLAY_HISTORY","methodology":VERSION,"windows":[]}
    prices=[float(r["close"]) for r in rows];volumes=[int(r["volume"]) for r in rows]
    signals=[]
    for i in range(252,len(rows)-1):
        m=metrics(prices[i-252:i+1],volumes[i-252:i+1])
        if m and m["status"]=="FIP_PRICE_MATCH":signals.append(i)
    # Fixed chronological split; no learning or tuning, no positions crossing
    # boundaries, next completed close entry, fixed holding observation count.
    split=max(253,int(len(rows)*.7))
    result=[]
    for hold in (20,60):
        folds=[]
        for name,start,end in (("EARLIER",253,split),("LATER",split,len(rows))):
            changes=[];downsides=[];last=-1
            for signal in signals:
                entry=signal+1;exit=entry+hold
                if signal<start-1 or entry<start or exit>=end or entry<=last:continue
                path=prices[entry:exit+1];changes.append(path[-1]/path[0]-1)
                peak=path[0];dd=0.
                for v in path:peak=max(peak,v);dd=min(dd,v/peak-1)
                downsides.append(dd*100);last=exit
            folds.append({"period":name,"first_date":rows[start]["trade_date"] if start<len(rows) else None,
                "last_date":rows[end-1]["trade_date"] if end>start else None,"positions":len(changes),
                "worst_close_drawdown_percent":round(min(downsides),4) if downsides else None,
                "cost_scenarios":[{"cost_bps_per_side":bps,"mean_net_change_percent":round(mean(net)*100,4),"positive_count":sum(x>0 for x in net)}
                    for bps in (15,30,60) if (net:=[(1+x)*(1-bps/10000)**2-1 for x in changes])]})
        result.append({"holding_observations":hold,"folds":folds})
    return {"status":"DESCRIPTIVE_FIXED_RULE_REPLAY","methodology":VERSION,"windows":result,"signal_count":len(signals),
        "as_of":rows[-1]["trade_date"],"notice":"Fixed rules, next closing mark, nonoverlapping positions, earlier/later disjoint windows. No fitting, no execution, no point-in-time universe or independent walk-forward certification."}

def rank(snapshot,instant):
    today=instant.astimezone(IST).date()
    summary={"methodology":VERSION,"status":"AWAITING_STRICT_HISTORY","eligible_listings":0,"matched_listings":0,"matched_companies":0,
        "exclusions":{},"items":[],"notice":NOTICE}
    if not snapshot.get("enabled"):return summary
    groups=defaultdict(list);reasons=Counter();observations=company_venues.collect(snapshot,instant)
    for section in snapshot.get("sections",[]):
        venue=section.get("section")
        if venue not in ("NSE","BSE") or section.get("status")!="READY":continue
        result=section.get("result") or {};coverage=result.get("discovery_coverage") or {}
        if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":continue
        rows=result.get("company_research_universe") or []
        if not isinstance(rows,list) or len(rows)>20000:continue
        counts=Counter(r.get("isin") for r in rows if isinstance(r,dict))
        for row in rows:
            f=row.get("fip_research") or {};isin=row.get("isin")
            if not exact_isin(isin) or counts[isin]!=1 or row.get("exchange")!=venue or row.get("as_of")!=coverage.get("expected_session") or row.get("security_state") in company_venues.SPECIAL:continue
            if f.get("methodology")!=VERSION or f.get("calendar_status")!="STORED_SESSIONS_MATCHED" or f.get("as_of")!=row.get("as_of") or f.get("adjustment_status")!="ADJUSTED":continue
            summary["eligible_listings"]+=1
            if f.get("status")!="FIP_PRICE_MATCH":
                reasons.update(f.get("exclusions",[]));continue
            score=f.get("score")
            if type(score) not in (int,float) or not isfinite(score) or not 0<=score<=100:continue
            listings=[r for r in observations.get(isin,[]) if r["exchange"]==venue and r["id"]==row.get("id") and r.get("as_of")==row["as_of"]]
            if len(listings)!=1:continue
            listing=listings[0]
            if listing.get("security_state") in company_venues.SPECIAL:continue
            groups[isin].append({**f,"isin":isin,"id":row["id"],"exchange":venue,"symbol":listing["symbol"],"close":listing["close"],
                "review_findings":sorted({v for r in observations[isin] for v in (r.get("exchange_surveillance") or {}).get("findings",[])}|{"REPORTED_"+r["security_state"]+"_AT_"+r["exchange"] for r in observations[isin] if r.get("security_state") in company_venues.SPECIAL})})
    summary["matched_listings"]=sum(len(v) for v in groups.values())
    def key(r):return (-r["score"],-r["median_daily_turnover_cr"],r["exchange"],r["id"])
    # Conflicting same-venue registry observations are not resolved by
    # selecting the better score; keep all cross-venue warnings.
    chosen=[min(v,key=key) for isin,v in groups.items()
        if len({r["exchange"] for r in observations[isin]})==len(observations[isin])]
    summary.update(matched_companies=len(chosen),items=sorted(chosen,key=key)[:10],exclusions=dict(reasons),
        status="PRICE_MATCHES_AVAILABLE" if chosen else "NO_PRICE_MATCHES" if summary["eligible_listings"] else "AWAITING_STRICT_HISTORY")
    return summary

def publish(snapshot,connect,instant):
    from . import watch_outcomes
    today=instant.astimezone(IST).date()
    report=rank(snapshot,instant)
    with closing(connect()) as db,db:
        watch_outcomes._table(db)
        db.execute("BEGIN IMMEDIATE")
        # Freeze one company per observed date, even if venue preference
        # changes before a subsequent scheduler pass.
        existing=set()
        for saved in db.execute("SELECT observed_date,evidence FROM watch_outcomes WHERE horizon=? AND observed_date>=?",(HORIZON,(today-timedelta(days=4)).isoformat())):
            try:existing.add((saved["observed_date"],json.loads(saved["evidence"]).get("isin")))
            except (ValueError,TypeError,KeyError):continue
        for row in report["items"]:
            if (row["as_of"],row["isin"]) in existing:continue
            if row["review_findings"] or not isinstance(row["close"],(int,float)) or not isfinite(row["close"]) or row["close"]<=0:continue
            evidence={k:row[k] for k in ("symbol","exchange","close","adjustment_status","as_of","isin")}
            evidence.update(methodology=VERSION,fip_score=row["score"],fip_windows=row["windows"],fip_history_fingerprint=row["history_fingerprint"])
            existing.add((row["as_of"],row["isin"]))
            db.execute("""INSERT OR IGNORE INTO watch_outcomes(instrument_id,horizon,observed_date,published_at,maturity_date,evidence)
                VALUES(?,?,?,?,?,?)""",(row["id"],HORIZON,row["as_of"],instant.isoformat(),(today+timedelta(days=DAYS)).isoformat(),json.dumps(evidence,allow_nan=False)))

def prospective(connect,instant):
    from . import watch_outcomes,research_reliability as rel
    today=instant.astimezone(IST).date()
    with closing(connect()) as db:
        watch_outcomes._table(db)
        rows=db.execute("""SELECT * FROM watch_outcomes WHERE horizon=? AND published_at>=? ORDER BY published_at,instrument_id,observed_date LIMIT 5001""",
            (HORIZON,(instant-timedelta(days=366)).isoformat())).fetchall()
    selected=[];last={};immature=overlap=0
    for row in rows[:5000]:
        try:
            e=json.loads(row["evidence"]);isin=e.get("isin");score=e.get("fip_score")
            published=rel._stamp(row["published_at"]);maturity=date.fromisoformat(row["maturity_date"])
            if not exact_isin(isin) or e.get("methodology")!=VERSION or e.get("adjustment_status")!="ADJUSTED" or type(score) not in (float,int) or not isfinite(score) or not 0<=score<=100 or not 1<=(published-date.fromisoformat(row["observed_date"])).days<=4 or maturity!=published+timedelta(days=DAYS) or not today-timedelta(days=365)<=published<=today:continue
            if today<=maturity+timedelta(days=7):immature+=1;continue
            if isin in last and published<=last[isin]:overlap+=1;continue
            last[isin]=maturity+timedelta(days=7)
            try:change=rel._outcome(row,published,maturity,today)
            except (ValueError,KeyError,TypeError,OverflowError):change=None
            selected.append((isin,published,score,change,rel._path_metrics(row,change)))
        except (ValueError,KeyError,TypeError,OverflowError):continue
    bands=[]
    for label,lo,hi in (("50_TO_BELOW_65",0,65),("65_TO_BELOW_80",65,80),("80_OR_ABOVE",80,101)):
        sample=[r for r in selected if lo<=r[2]<hi];observed=[r for r in sample if r[3] is not None]
        coverage=len(observed)/len(sample) if sample else 0;paths=[r[4][2] for r in observed if r[4] is not None]
        distinct=len({r[0] for r in observed});dates=len({r[1] for r in observed})
        bands.append({"band":label,"mature_count":len(sample),"observed_count":len(observed),"coverage_percent":round(coverage*100,2),
            "distinct_isins":distinct,"publication_dates":dates,"observed_paths":len(paths),"median_close_drawdown_percent":round(median(paths),4) if paths else None,
            "status":"DESCRIPTIVE_SAMPLE_AVAILABLE" if len(rows)<=5000 and len(observed)>=30 and distinct>=10 and dates>=10 and coverage>=.8 else "INSUFFICIENT_EVIDENCE",
            "cost_scenarios":[{"cost_bps_per_side":bps,"mean_net_change_percent":round(mean(net)*100,4),"positive_count":sum(v>0 for v in net)} for bps in (15,30,60) if (net:=[(1+r[3])*(1-bps/10000)**2-1 for r in observed])]})
    return {"methodology":VERSION,"status":"DESCRIPTIVE_BAND_EVIDENCE" if any(b["status"]=="DESCRIPTIVE_SAMPLE_AVAILABLE" for b in bands) else "AWAITING_MATURE_EVIDENCE",
        "selected_mature":len(selected),"immature":immature,"overlap_excluded":overlap,"truncated":len(rows)>5000,"bands":bands,
        "calibrated":False,"probability":None,"notice":"Frozen FIP score at original watch publication; 60-calendar-day prospective review, same verified outcome policy as daily watches. Missing outcomes retained; no calibrated confidence."}
