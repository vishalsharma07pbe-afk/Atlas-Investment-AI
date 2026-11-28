"""Bounded local history paging and cross-page top-k merging.

Only publish a broad result after processing the observed registry count.
Registry count changes, duplicate cursors, session rollover and deadlines fail
closed. This is not an atomic database snapshot or complete exchange coverage.
"""
from collections import Counter
from time import monotonic
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

PAGE=200
MAX_LISTINGS=20000
DEADLINE_SECONDS=480

def _top(rows,key,n=5):
    return sorted(rows,key=key)[:n]

def _counts(a,b):
    return dict(Counter(a)+Counter(b))

def _gainer(r): return (-r["change_1d_percent"],r["exchange"],r["symbol"],r["id"])
def _loser(r): return (r["change_1d_percent"],r["exchange"],r["symbol"],r["id"])
def _momentum(r): return (-r["momentum_20d_percent"],r["symbol"],r["id"])
def _horizon(r): return (-r["rank_score"],r["exchange"],r["symbol"],r["id"])
def _pressure(r): return (-r["price_volume_pressure"]["relative_volume"],r["symbol"],r["id"])
def _trap(r): return (not any(e["status"]=="REENTRY_OBSERVED" for e in r["followthrough"]["events"]),
    -max(abs(e["break_percent"]) for e in r["followthrough"]["events"]),r["symbol"],r["id"])

def merge(out,page):
    if out is None:
        return page
    for k in ("universe_size","eligible_count","annual_depth_count"):
        out[k]+=page[k]
    for key,value in page["skipped"].items():
        out["skipped"][key]=out["skipped"].get(key,0)+value
    for key,rank in (("top_gainers",_gainer),("top_losers",_loser),("momentum_leaders",_momentum)):
        out[key]=_top(out[key]+page[key],rank)
    for key in ("company_research_universe","replay_research_universe","steady_momentum_candidates","venue_observations"):
        out.setdefault(key,[]).extend(page.get(key,[]))
    for h,g in out["horizons"].items():
        p=page["horizons"][h]
        for key in ("matched_count","evaluated_count"):g[key]+=p[key]
        g["exclusions"]=_counts(g["exclusions"],p["exclusions"])
        g["candidates"]=_top(g["candidates"]+p["candidates"],_horizon)
        g["status"]="TECHNICAL_WATCH_ONLY" if g["candidates"] else "NO_QUALIFIED_EVIDENCE"
    for h,g in out["history_coverage"].items():
        g["eligible_histories"]+=page["history_coverage"][h]["eligible_histories"]
    a=out["sample_breadth"];b=page["sample_breadth"]
    pairs={r["previous_session"]:r.copy() for r in a["pairs"]}
    for row in b["pairs"]:
        target=pairs.setdefault(row["previous_session"],{"previous_session":row["previous_session"],"advancing":0,"declining":0,"unchanged":0})
        for k in ("advancing","declining","unchanged"):target[k]+=row[k]
    a["pairs"]=[pairs[k] for k in sorted(pairs)]
    a=out["corporate_action_review"];b=page["corporate_action_review"]
    for k in ("normalized_preview_count","withheld_count","provider_crossing_count"):a[k]+=b[k]
    for k in ("previews","provider_crossings"):a[k]=(a[k]+b[k])[:5]
    a=out["breakout_review"];b=page["breakout_review"]
    for k in ("evaluated_count","event_listing_count"):a[k]+=b[k]
    a["items"]=_top(a["items"]+b["items"],_trap)
    a=out["price_volume_review"];b=page["price_volume_review"]
    for k in ("evaluated_count","flagged_count"):a[k]+=b[k]
    for k in ("downside_items","upside_items"):a[k]=_top(a[k]+b[k],_pressure)
    return out

def scan(exchange,load,process,clock):
    start=monotonic()
    instant=clock()
    cutoff=instant.isoformat()
    checked_day=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    if exchange not in ("NSE","BSE"):raise ValueError("INVALID_EXCHANGE")
    cursor=0
    observed=None
    seen=0
    result=None
    while True:
        if monotonic()-start>DEADLINE_SECONDS:raise TimeoutError("DISCOVERY_SCAN_DEADLINE")
        page=load("/api/v1/market-data/discovery-universe-page?"+urlencode({"exchange":exchange,"afterId":cursor,"cutoff":cutoff}))
        if not isinstance(page,list) or len(page)>PAGE:raise ValueError("INVALID_DISCOVERY_PAGE")
        if not page:
            if observed is not None and seen!=observed[0]:raise ValueError("DISCOVERY_SCAN_INCOMPLETE")
            break
        ids=[r.get("id") if isinstance(r,dict) else None for r in page]
        if any(type(i) is not int or i<=cursor for i in ids) or ids!=sorted(set(ids)):
            raise ValueError("INVALID_DISCOVERY_CURSOR")
        signatures={(r.get("recent_registry_count"),r.get("expected_session"),r.get("expected_session_count")) for r in page}
        if len(signatures)!=1:raise ValueError("DISCOVERY_UNIVERSE_CHANGED")
        signature=next(iter(signatures))
        if type(signature[0]) is not int or not 1<=signature[0]<=MAX_LISTINGS or signature[0]<seen+len(page):
            raise ValueError("DISCOVERY_SCAN_BOUND_OR_COUNT")
        if observed is not None and signature!=observed:raise ValueError("DISCOVERY_UNIVERSE_CHANGED")
        observed=signature
        part=process(exchange,page,cutoff)
        if part["discovery_coverage"]["calendar_checked_on"]!=checked_day.isoformat() or part["universe_size"]!=len(page):
            raise ValueError("DISCOVERY_SCAN_SESSION_CHANGED")
        result=merge(result,part)
        seen+=len(page)
        cursor=ids[-1]
    if clock().astimezone(ZoneInfo("Asia/Kolkata")).date()!=checked_day or monotonic()-start>DEADLINE_SECONDS:
        raise ValueError("DISCOVERY_SCAN_EXPIRED")
    if result is None:result=process(exchange,[],cutoff)
    coverage=result["discovery_coverage"]
    coverage.update({"selected_count":seen,"recent_registry_count":seen,"selection_limit":None,
        "selection_method":"ALL_LOCALLY_RECENT_HISTORIES_KEYSET_SCAN",
        "scan_complete":True,"page_size":PAGE,"safety_bound":MAX_LISTINGS,
        "scan_scope":"LOCAL_RECENT_HISTORIES_ONLY","observation_cutoff":cutoff,
        "annual_depth_count":result["annual_depth_count"]})
    result["notice"]="All locally recent active cash-equity histories observed in this completed paged sweep. Not all exchange listings have history; no live or qualified investment ranking is implied."
    result["sample_breadth"]["notice"]="Comparable adjusted histories in the completed local sweep; not official exchange breadth."
    return result
