"""Typed public-only projections of already-authorized saved research.

No free-text provider fields, URLs, raw articles, local deals, owner-specific
data, credentials or trade instructions. All output keys and string domains
are explicitly enumerated. Never make a new provider request here.
"""
from datetime import date,datetime,timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from .replay_evidence import exact_isin
from .global_context import GROUPS

IST=ZoneInfo("Asia/Kolkata")
DOMAINS={"ownership_context":"OWN","peer_valuation":"VAL","news_topics":"NEWS",
         "global_changes":"GLOBAL","benchmark_regime":"REGIME","market_flows":"FLOWS"}
OWNERS=("promoters","fii","other_dii","mutual_funds","retail_and_other")
TOPICS=("EARNINGS","REGULATORY","CORPORATE_ACTION","TRANSACTION","MANAGEMENT")
DIRECTIONS=("NET_BUYING_MAJORITY","NET_SELLING_MAJORITY","MIXED_OR_BALANCED")

def _num(v,low=-1e9,high=1e9):
    return type(v) in (int,float) and isfinite(v) and low<=v<=high

def _day(v):
    d=date.fromisoformat(v)
    if d.isoformat()!=v:
        raise ValueError("INVALID_DATE")
    return d

def _stamp_day(v):
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP")
    return d.astimezone(IST).date()

def _ownership(company,today):
    block=company.get("ownership_research") or {}
    if block.get("status") not in ("COMPARABLE_QUARTERS","LATEST_QUARTER_ONLY"):
        return None
    latest=_day(block["latest_period"])
    if not 0<=(today-latest).days<=150:
        return None
    rows=block.get("categories",[])
    if len(rows)!=5 or {r.get("category") for r in rows}!=set(OWNERS):
        return None
    comparable=block["status"]=="COMPARABLE_QUARTERS"
    prior=_day(block["previous_period"]) if comparable else None
    if prior and not 89<=(latest-prior).days<=93:
        return None
    output=[]
    for r in rows:
        v=r.get("latest_percent")
        p=r.get("previous_percent")
        delta=r.get("change_pp")
        if not _num(v,0,100):
            return None
        if comparable and (not _num(p,0,100) or not _num(delta,-100,100) or abs(v-p-delta)>0.0001):
            return None
        output.append({"category":r["category"],"latest_percent":v,
                       "previous_percent":p if comparable else None,"change_pp":delta if comparable else None})
    if not 99.5<=sum(r["latest_percent"] for r in output)<=100.5:
        return None
    if comparable and not 99.5<=sum(r["previous_percent"] for r in output)<=100.5:
        return None
    return {"basis":"PROVIDER_REPORTED_QUARTERLY_PERCENTAGES_NOT_TRANSACTIONS",
            "latest_period":latest.isoformat(),"previous_period":prior.isoformat() if prior else None,
            "categories":sorted(output,key=lambda r:r["category"])}

def _valuation(company,today):
    block=(company.get("peer_research") or {}).get("valuation_research") or {}
    if block.get("status")!="UNDATED_PEER_MULTIPLES":
        return None
    output=[]
    for key in ("PE","PB","EV_EBITDA"):
        rows=[r for r in block.get("metrics",[]) if r.get("metric")==key]
        if len(rows)!=1:
            continue
        r=rows[0]
        stamp=_stamp_day(r["company_retrieved_at"])
        a,b,delta=r.get("company_value"),r.get("peer_median"),r.get("premium_discount_percent")
        if (r.get("observation_period")!="UNVERIFIED" or r.get("peer_count")!=3
            or not 0<=(today-stamp).days<=1 or not _num(a,0.000001) or not _num(b,0.000001)
            or not _num(delta) or abs(100*(a/b-1)-delta)>0.001):
            continue
        output.append({"metric":key,"company_multiple":a,"peer_median":b,"peer_count":3,
                       "premium_discount_percent":delta,"retrieval_date":stamp.isoformat()})
    return {"basis":"UNDATED_PROVIDER_MULTIPLES_NOT_FAIR_VALUE","metrics":output} if output else None

def _news(candidate,today):
    block=candidate.get("news_evidence") or {}
    if block.get("status")!="REVIEW_AVAILABLE":
        return None
    # A cross-venue company headline is valid only with exact source identity.
    if candidate.get("exchange")!="NSE" and not (
        block.get("scope")=="PUBLIC_COMPANY_HEADLINE_OBSERVATIONS" and exact_isin(candidate.get("isin"))
        and block.get("isin")==candidate["isin"] and block.get("source_exchange")=="NSE"
        and block.get("source_instrument_key")=="NSE_EQ|"+candidate["isin"]):
        return None
    if not 0<=(today-_stamp_day(block["retrieved_at"])).days<=1:
        return None
    output=set()
    for r in block.get("articles",[])[:10]:
        if r.get("source_provider")!="UPSTOX_NEWS" or r.get("sentiment")!="NOT_ANALYZED":
            continue
        d=_stamp_day(r["published_at"])
        if 0<=(today-d).days<=3:
            output.update((d.isoformat(),t) for t in TOPICS if t in r.get("topics",[]))
    return {"basis":"UNVERIFIED_PROVIDER_HEADLINE_TOPIC_NOT_CONFIRMED_EVENT",
            "source_exchange":"NSE","observations":[{"publication_date":d,"topic":t} for d,t in sorted(output)]} if output else None

def _global(context,today):
    block=context.get("global_context") or {}
    if block.get("status") not in ("AVAILABLE","PARTIAL"):
        return None
    all_rows=[r for g in block.get("groups",[]) for r in g.get("items",[])]
    output=[]
    for group,keys in GROUPS.items():
        for key in keys:
            rows=[r for r in all_rows if r.get("key")==key]
            if len(rows)!=1:
                continue
            r=rows[0]
            d=_day(r["as_of"])
            change=r.get("change") or {}
            unit="BASIS_POINTS" if group=="US_YIELDS" else "PERCENT"
            age=10 if group=="OIL" else 5 if group in ("CURRENCIES","US_YIELDS") else 7
            if (not 0<=(today-d).days<=age or change.get("unit")!=unit or change.get("end_date")!=d.isoformat()
                    or not _num(change.get("value")) or not 1<=(d-_day(change["start_date"])).days<=14):
                continue
            output.append({"indicator":key,"start_date":change["start_date"],"end_date":d.isoformat(),
                           "change":change["value"],"unit":unit})
    return {"basis":"FIVE_AVAILABLE_OBSERVATION_CHANGES_NOT_SYNCHRONIZED","observations":output} if output else None

def _regime(context,observed):
    r=context.get("market_regime") or {}
    if (r.get("status")!="OBSERVED_BENCHMARK_REGIME" or r.get("as_of")!=observed
        or r.get("trend") not in ("RISING","FALLING","SIDEWAYS")
        or r.get("volatility_regime") not in ("HIGH_HISTORICAL_VOLATILITY","BELOW_HIGH_THRESHOLD")
        or not _num(r.get("benchmark_change_60_percent"),-100)
        or not _num(r.get("volatility_20_annualized_percent"),0)):
        return None
    return {"basis":"NIFTY50_PRICE_INDEX_HISTORICAL_OBSERVATION","as_of":observed,
            **{k:r[k] for k in ("trend","volatility_regime","benchmark_change_60_percent","volatility_20_annualized_percent")}}

def _flows(context,observed):
    report=context.get("market_regime") or {}
    block=report.get("institutional") or {}
    if not _regime(context,observed) or block.get("status")!="MATCHED_REPORTED_SESSIONS":
        return None
    dates=report.get("last_five_sessions",[])
    if (len(dates)!=5 or dates!=sorted(set(dates),reverse=True) or dates[0]!=observed
        or not 1<=(_day(dates[0])-_day(dates[-1])).days<=14
        or any(_day(d)>_day(observed) for d in dates)
        or block.get("fii") not in DIRECTIONS or block.get("dii") not in DIRECTIONS):
        return None
    return {"basis":"NSE_CASH_MARKET_LEVEL_REPORTED_FLOWS_NOT_STOCK_TRANSACTIONS",
            "dates":dates,"fii":block["fii"],"dii":block["dii"]}

def summarize(candidate,context,observed):
    if context.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY" or context.get("enabled") is not True:
        return {}
    try:
        today=_day(context["research_date"])
        if not 0<=(today-_day(observed)).days<=7:
            return {}
    except (ValueError,TypeError,KeyError):
        return {}
    company=candidate.get("company_evidence") or {}
    same_company=exact_isin(candidate.get("isin")) and company.get("isin")==candidate["isin"]
    probes={"global_changes":lambda:_global(context,today),"benchmark_regime":lambda:_regime(context,observed),
            "market_flows":lambda:_flows(context,observed)}
    if exact_isin(candidate.get("isin")):
        probes["news_topics"]=lambda:_news(candidate,today)
    if same_company:
        probes.update(ownership_context=lambda:_ownership(company,today),peer_valuation=lambda:_valuation(company,today))
    result={}
    for key,fn in probes.items():
        try:
            value=fn()
            if value:
                result[key]=value
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
            # One malformed or unavailable domain does not contaminate others.
            continue
    return result
