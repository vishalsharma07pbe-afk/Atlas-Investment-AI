"""Matched current local sector/industry price observations, not an index or forecast."""
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
from contextlib import closing
from datetime import date,timedelta
from math import isfinite
from zoneinfo import ZoneInfo
import json
import re

from . import automatic_company_evidence,peer_research
from .relative_strength import WINDOWS,date_digest
from .replay_evidence import exact_isin,full_manifest

VERSION="MATCHED-CLASSIFICATION-PRICE-1"
NOTICE=("Same-exchange, same ordered observed dates, provider-validated adjusted single-source histories, "
        "fresh provider sector/industry labels. Equal-company local sample excluding the subject ISIN, not an official "
        "index, total return, complete market coverage or historical point-in-time membership. Classification is current, "
        "sample includes non-shortlisted histories. Matching observed dates does not establish calendar completeness. "
        "No ranking/qualification promotion or forecast.")
MINIMUM={"sector":5,"industry":3}
SPECIAL={"PCA","SME","RELIST","IPO","SUSPENDED_REPORTED"}

def windows(raw,today):
    # Validate a single largest usable suffix instead of hashing four entire
    # manifests for each listing. If an older invalid row prevents a long
    # window, a separately validated shorter suffix is still eligible.
    for n in reversed(WINDOWS):
        if len(raw)<n+1:continue
        sample=raw[-n-1:]
        audit=full_manifest(sample,today)
        if audit is None or len(audit["observations"])!=n+1:continue
        dates=list(audit["observations"])
        result={}
        for length in WINDOWS:
            if length>n:continue
            d=dates[-length-1:]
            change=100*(float(sample[-1]["close"])/float(sample[-length-1]["close"])-1)
            if isfinite(change) and -100<change<=1e9:
                result[str(length)]={"first_date":d[0],"last_date":d[-1],"dates_digest":date_digest(d),
                    "return_percent":round(change,6),"source_code":sample[-1]["source_code"]}
        return result
    return {}

def _point(value,as_of):
    if not isinstance(value,dict):return None
    try:
        a,b=date.fromisoformat(value["first_date"]),date.fromisoformat(value["last_date"])
        digest=value["dates_digest"];source=value["source_code"];v=value["return_percent"]
        if b.isoformat()!=as_of or a>=b or not re.fullmatch(r"[a-f0-9]{64}",digest) or not re.fullmatch(r"[A-Z0-9_-]{1,40}",source) or type(v) not in (float,int) or not isfinite(v) or not -100<v<=1e9:
            return None
        return (a.isoformat(),b.isoformat(),digest,source),v
    except (ValueError,TypeError,KeyError):return None

def _classifications(connect,instant):
    with closing(connect()) as db:
        automatic_company_evidence._table(db)
        rows=db.execute("SELECT isin,payload FROM automatic_company_evidence WHERE status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?",
            ((instant-timedelta(hours=24)).isoformat(),instant.isoformat())).fetchall()
    result={}
    for row in rows:
        try:
            r=json.loads(row["payload"])
            if r.get("isin")!=row["isin"] or not exact_isin(row["isin"]):continue
            sector=peer_research.fresh_sector(r,instant)
            if not sector or len(sector)>120:continue
            industry=peer_research.fresh_classification(r,instant)
            result[row["isin"]]=(sector,industry[1] if industry and len(industry[1])<=120 else None)
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return result

def _median_without(values,value):
    # Sorted cohort contains exactly one observation from the subject.
    i=bisect_left(values,value)
    n=len(values)-1
    def at(k):return values[k+(k>=i)]
    return at(n//2) if n%2 else (at(n//2-1)+at(n//2))/2

def analyze(snapshot,classification,today):
    coverage={"methodology":VERSION,"status":"AWAITING_EVIDENCE","eligible_identities":0,"classified_identities":0,
        "comparable_identities":0,"venue_counts":{},"notice":NOTICE}
    indexed={}
    buckets=defaultdict(list)
    for market in ("NSE","BSE"):
        sections=[s for s in snapshot.get("sections",[]) if s.get("section")==market and s.get("status")=="READY"]
        if len(sections)!=1:continue
        result=sections[0].get("result") or {};meta=result.get("discovery_coverage") or {}
        if meta.get("calendar_checked_on")!=today.isoformat() or meta.get("calendar_status")!="PUBLISHED_SESSION":continue
        expected=meta.get("expected_session")
        try:
            if not 1<=(today-date.fromisoformat(expected)).days<=4:continue
        except (ValueError,TypeError):continue
        rows=result.get("company_research_universe")
        if not isinstance(rows,list) or len(rows)>20000:continue
        # Identity conflicts within a venue are withheld, not averaged or
        # resolved based on return. One company can appear on both venues.
        counts=Counter(r.get("isin") for r in rows if isinstance(r,dict) and exact_isin(r.get("isin")))
        ids=Counter(r.get("id") for r in rows if isinstance(r,dict) and type(r.get("id")) is int)
        stats={"eligible":0,"classified":0,"with_adjusted_windows":0}
        coverage["venue_counts"][market]=stats
        for r in rows:
            if not isinstance(r,dict):continue
            isin=r.get("isin");ident=r.get("id")
            if not exact_isin(isin) or counts[isin]!=1 or type(ident) is not int or ident<=0 or ids[ident]!=1 or r.get("exchange")!=market or r.get("as_of")!=expected or r.get("security_state") in SPECIAL:continue
            stats["eligible"]+=1
            labels=classification.get(isin)
            if not labels:continue
            stats["classified"]+=1
            points={}
            for n in WINDOWS:
                p=_point((r.get("comparative_price_windows") or {}).get(str(n)),expected)
                if not p:continue
                scope,v=p
                for kind,label in zip(("sector","industry"),labels):
                    if not label:continue
                    group=(market,kind,label,labels[0],n,*scope)
                    buckets[group].append(v)
                    points[(kind,n)]=(group,v)
            if points:
                stats["with_adjusted_windows"]+=1
                indexed[(market,isin)]=(ident,expected,labels,points)
    for values in buckets.values():values.sort()
    output={}
    regime=snapshot.get("market_regime") or {}
    for (market,isin),(ident,as_of,labels,points) in indexed.items():
        result={"methodology":VERSION,"status":"INSUFFICIENT_MATCHED_PEERS","exchange":market,"isin":isin,"id":ident,
                "as_of":as_of,"sector":labels[0],"industry":labels[1],"sector_windows":{},"industry_windows":{},"notice":NOTICE}
        for (kind,n),(group,value) in points.items():
            values=buckets[group]
            peer_count=len(values)-1
            if peer_count<MINIMUM[kind]:continue
            mid=_median_without(values,value)
            lower=bisect_left(values,value);higher=len(values)-bisect_right(values,value)
            equal=peer_count-lower-higher
            first,last,digest,source=group[-4:]
            benchmark=(regime.get("relative_strength_windows") or {}).get(str(n)) or {}
            calendar_match=(market=="NSE" and regime.get("status")=="OBSERVED_BENCHMARK_REGIME" and regime.get("calendar_checked_on")==today.isoformat() and regime.get("as_of")==as_of and benchmark.get("dates_digest")==digest and benchmark.get("first_date")==first and benchmark.get("last_date")==last)
            result[kind+"_windows"][str(n)]={"stock_return_percent":value,"peer_median_return_percent":round(mid,6),
                "difference_pp":round(value-mid,4),"peer_count":peer_count,"peers_below":lower,"peers_equal":equal,"peers_above":higher,
                "peer_percentile":round(100*(lower+.5*equal)/peer_count,2),"first_date":first,"last_date":last,
                "source_code":source,"calendar_status":"MATCHED_STORED_NSE_INDEX_SESSIONS" if calendar_match else "MATCHED_OBSERVED_DATES_ONLY"}
        if result["sector_windows"] or result["industry_windows"]:
            result["status"]="MATCHED_LOCAL_PEER_OBSERVATIONS"
            output[(market,isin,ident,as_of)]=result
    coverage.update(eligible_identities=sum(v["eligible"] for v in coverage["venue_counts"].values()),
        classified_identities=sum(v["classified"] for v in coverage["venue_counts"].values()),
        comparable_identities=len(output),status="MATCHED_LOCAL_PEER_OBSERVATIONS" if output else "INSUFFICIENT_MATCHED_PEERS")
    return output,coverage

def attach(snapshot,connect,instant):
    summary={"methodology":VERSION,"status":"DISABLED_OR_NOT_AUTHORIZED","notice":NOTICE}
    snapshot["sector_price_context"]=summary
    if not snapshot.get("enabled") or not automatic_company_evidence.permitted():return snapshot
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    classifications=_classifications(connect,instant)
    reports,summary=analyze(snapshot,classifications,today)
    snapshot["sector_price_context"]=summary
    # The official index comparison is independent of peer cohort size.
    from . import sector_benchmarks
    sector_benchmarks.attach_candidates(snapshot,classifications,today)
    for item,isin in automatic_company_evidence.identify_priority(snapshot):
        item.pop("sector_price_context",None)
        key=(item["exchange"],isin,item.get("id"),item.get("as_of"))
        if key in reports:item["sector_price_context"]=reports[key]
    return snapshot
