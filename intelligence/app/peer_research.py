"""Bounded provider-reported peer comparison using the existing company cache.

A peer list is not an industry census. Compare only explicitly identified
same-sector peers with consolidated annual statements for identical periods
and units. Never interpret sector market cap as company market cap or revenue
scale as market share. No provider calls or private fields in this module.
"""
from datetime import datetime,timedelta
from math import isfinite
from .fundamental_quality import ALIASES, _name
from statistics import median
import re

MAX_PEERS=3
MAX_ROTATION=60
KEY=re.compile(r"^(NSE|BSE)_EQ\|(IN[A-Z0-9]{10})$")


def sector(report):
    section=report.get("sections",{}).get("profile",{})
    if section.get("status")!="AVAILABLE":
        return None
    value=(section.get("data") or {}).get("sector")
    return " ".join(value.casefold().split()) if isinstance(value,str) and value.strip() else None


def selected(report):
    target=sector(report)
    if not target:
        return []
    seen=set()
    result=[]
    block=report.get("sections",{}).get("competitors",{})
    rows=block.get("data") or [] if block.get("status")=="AVAILABLE" else []
    for row in rows:
        if not isinstance(row,dict):
            continue
        key=row.get("instrument_key")
        match=KEY.fullmatch(key) if isinstance(key,str) else None
        raw_sector=row.get("sector")
        if not match or not isinstance(raw_sector,str) or " ".join(raw_sector.casefold().split())!=target:
            continue
        isin=match.group(2)
        if isin==report.get("isin") or isin in seen:
            continue
        seen.add(isin)
        result.append((isin,key))
        if len(result)>=MAX_PEERS:
            break
    return result


def _metric(report,key):
    if key in ("NET_MARGIN","OPERATING_MARGIN"):
        items=(report.get("fundamental_quality") or {}).get("derived_metrics",[])
    else:
        items=(report.get("financial_trends") or {}).get("items",[])
    matches=[r for r in items if r.get("metric")==("REVENUE" if key=="REVENUE_GROWTH" else key)]
    if len(matches)!=1:
        return None
    row=matches[0]
    period=row.get("latest_period")
    if not isinstance(period,str) or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])",period):
        return None
    if key in ("NET_MARGIN","OPERATING_MARGIN"):
        if row.get("unit")!="PERCENT":
            return None
        # The derived margin must come from current same-period consolidated
        # source trends, not just a coincidentally matching displayed label.
        source_keys=("REVENUE","NET_PROFIT" if key=="NET_MARGIN" else "OPERATING_PROFIT")
        source_rows=(report.get("financial_trends") or {}).get("items",[])
        for source_key in source_keys:
            source=[r for r in source_rows if r.get("metric")==source_key]
            if len(source)!=1 or source[0].get("statement_type")!="consolidated" or source[0].get("latest_period_may_be_stale") is not False or source[0].get("period_basis")!="DECLARED_ANNUAL_MONTH_END" or source[0].get("latest_period")!=period:
                return None
        value=row.get("latest_value")
        unit="PERCENT"
    else:
        if row.get("period_basis")!="DECLARED_ANNUAL_MONTH_END" or row.get("statement_type")!="consolidated" or row.get("latest_period_may_be_stale") is not False:
            return None
        if str(row.get("unit","")).casefold().strip() not in ("crore","inr crore"):
            return None
        value=row.get("latest_value") if key=="REVENUE" else row.get("change_percent")
        unit="INR_CRORE" if key=="REVENUE" else "PERCENT"
    if type(value) not in (float,int) or not isfinite(value):
        return None
    if key=="REVENUE" and value<=0:
        return None
    if key=="REVENUE_GROWTH":
        prior=row.get("previous_period")
        if not isinstance(prior,str) or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])",prior):
            return None
        period=prior+" / "+period
    return period,unit,value


VALUATION_METRICS=("PE","PB","EV_EBITDA")


def _industry(report):
    block=report.get("sections",{}).get("profile",{})
    value=(block.get("data") or {}).get("industry") if block.get("status")=="AVAILABLE" else None
    return " ".join(value.casefold().split()) if isinstance(value,str) and value.strip() else None


def _valuation_multiple(report,key):
    """Provider-reported company multiple only; observation basis is unverified."""
    block=report.get("sections",{}).get("ratios",{})
    rows=block.get("data") if block.get("status")=="AVAILABLE" else None
    source=block.get("source")
    if not isinstance(rows,list) or not isinstance(source,dict) or source.get("provider")!="UPSTOX":
        return None
    isin=report.get("isin")
    if not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin) or source.get("endpoint")!=f"/v2/fundamentals/{isin}/key-ratios":
        return None
    try:
        retrieved=datetime.fromisoformat(source["retrieved_at"])
        if retrieved.tzinfo is None:
            return None
    except (ValueError,TypeError,KeyError,OverflowError):
        return None
    matches=[row for row in rows if isinstance(row,dict) and _name(row.get("name")) in ALIASES[key]]
    if len(matches)!=1:
        return None
    value=matches[0].get("company_value")
    if matches[0].get("unit")!="RATIO" or type(value) not in (int,float) or not isfinite(value) or value<=0:
        return None
    return value,retrieved


def _valuation(report,compatible):
    industry=_industry(report)
    same_industry=[(isin,key,peer) for isin,key,peer in compatible if industry and _industry(peer)==industry]
    metrics=[]
    for metric in VALUATION_METRICS:
        target=_valuation_multiple(report,metric)
        if not target:
            continue
        value,stamp=target
        matched=[]
        for isin,key,peer in same_industry:
            observation=_valuation_multiple(peer,metric)
            if observation and abs(observation[1]-stamp)<=timedelta(hours=24):
                matched.append({"isin":isin,"instrument_key":key,"value":observation[0],
                                "retrieved_at":observation[1].isoformat()})
        if len(matched)<3:
            continue
        stamps=[stamp]+[datetime.fromisoformat(row["retrieved_at"]) for row in matched]
        if max(stamps)-min(stamps)>timedelta(hours=24):
            continue
        values=[row["value"] for row in matched]
        mid=median(values)
        premium=(value/mid-1)*100
        if not isfinite(premium):
            continue
        metrics.append({"metric":metric,"company_value":value,"peer_median":mid,
                        "peer_min":min(values),"peer_max":max(values),"peer_count":len(matched),
                        "premium_discount_percent":round(premium,4),"company_retrieved_at":stamp.isoformat(),
                        "observation_period":"UNVERIFIED","peers":matched})
    quality=report.get("fundamental_quality") or {}
    warnings=quality.get("warnings") or []
    discounted=[m["metric"] for m in metrics if m["company_value"]<m["peer_median"]]
    # A low multiple plus deterioration is a research prompt, never a value-trap diagnosis.
    review="DISCOUNT_WITH_REPORTED_DETERIORATION_REVIEW" if discounted and warnings else None
    return {"status":"UNDATED_PEER_MULTIPLES" if metrics else "INSUFFICIENT_COMPARABLE_MULTIPLES",
            "same_industry_cached_count":len(same_industry),"metrics":metrics,
            "discounted_metrics":discounted,"review_prompt":review,
            "quality_status":quality.get("status","UNAVAILABLE"),
            "observation_period_verified":False,"fair_value":None,"valuation_eligible":False,
            "notice":"Positive provider-reported company multiples within a 24-hour retrieval window, not matched valuation dates or earnings bases. Same-sector and same-industry sample only; not an industry-wide ranking. A discount is not undervaluation, and a premium is not overvaluation. No price target or forecast."}


def summarize(report,reports):
    peers=selected(report)
    compatible=[]
    for isin,key in peers:
        peer=reports.get(isin)
        if peer and peer.get("isin")==isin and sector(peer)==sector(report):
            compatible.append((isin,key,peer))
    metrics=[]
    for key in ("REVENUE","REVENUE_GROWTH","NET_MARGIN","OPERATING_MARGIN"):
        target=_metric(report,key)
        if not target:
            continue
        period,unit,value=target
        matched=[]
        for isin,instrument,peer in compatible:
            observation=_metric(peer,key)
            if observation and observation[:2]==(period,unit):
                matched.append({"isin":isin,"instrument_key":instrument,"value":observation[2]})
        if len(matched)<3:
            continue
        mid=median(r["value"] for r in matched)
        metrics.append({"metric":key,"period":period,"unit":unit,"company_value":value,
                        "peer_median":mid,"peer_count":len(matched),
                        "peers_above":sum(r["value"]>value for r in matched),
                        "peers_below":sum(r["value"]<value for r in matched),
                        "peers":matched})
    return {"status":"SAMPLED_PEER_COMPARISON" if metrics else "INSUFFICIENT_COMPARABLE_PEERS",
            "selected_peer_count":len(peers),"cached_same_sector_count":len(compatible),
            "minimum_peers_per_metric":3,"sample_limit":MAX_PEERS,"metrics":metrics,
            "valuation_research":_valuation(report,compatible),
            "notice":"Bounded provider-listed same-sector sample, not a market-leadership or market-share ranking. Annual figures are provider-reported, not independently filing-verified; differences in business mix remain possible. No fair-value estimate or investment qualification."}
