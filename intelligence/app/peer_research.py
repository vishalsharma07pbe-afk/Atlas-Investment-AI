"""Bounded provider-reported peer comparison using the existing company cache.

A peer list is not an industry census. Compare only explicitly identified
same-sector peers with consolidated annual statements for identical periods
and units. Never interpret sector market cap as company market cap or revenue
scale as market share. No provider calls or private fields in this module.
"""
from math import isfinite
from statistics import median
import re

MAX_PEERS=3
MAX_ROTATION=60
KEY=re.compile(r"^(NSE|BSE)_EQ\|(IN[A-Z0-9]{10})$")


def sector(report):
    section=report.get("sections",{}).get("profile",{})
    value=(section.get("data") or {}).get("sector")
    return " ".join(value.casefold().split()) if isinstance(value,str) and value.strip() else None


def selected(report):
    target=sector(report)
    if not target:
        return []
    seen=set()
    result=[]
    rows=report.get("sections",{}).get("competitors",{}).get("data") or []
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
    matches=[r for r in items if r.get("metric")==key]
    if len(matches)!=1:
        return None
    row=matches[0]
    period=row.get("latest_period")
    if not isinstance(period,str) or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])",period):
        return None
    if key in ("NET_MARGIN","OPERATING_MARGIN"):
        if row.get("unit")!="PERCENT":
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
    return period,unit,value


def summarize(report,reports):
    peers=selected(report)
    compatible=[]
    for isin,key in peers:
        peer=reports.get(isin)
        if peer and peer.get("isin")==isin and sector(peer)==sector(report):
            compatible.append((isin,key,peer))
    metrics=[]
    for key in ("REVENUE","NET_MARGIN","OPERATING_MARGIN"):
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
            "notice":"Bounded provider-listed same-sector sample, not a market-leadership or market-share ranking. Annual figures are provider-reported, not independently filing-verified; differences in business mix remain possible. No fair-value estimate or investment qualification."}
