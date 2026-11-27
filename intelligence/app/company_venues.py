"""Company-first, venue-aware public research; no trading or venue clearance."""
from collections import defaultdict
from datetime import date,datetime,timedelta
from math import isfinite
from statistics import median
from zoneinfo import ZoneInfo
from .replay_evidence import exact_isin

VERSION="COMPANY-VENUE-1"
SPECIAL=("PCA","SME","RELIST","IPO","SUSPENDED_REPORTED")
NOTICE=("One ISIN per company shortlist. Observed venues are from the current local registry/history sample only, "
        "not proof of all listings. Historical turnover is a proxy; a fresh paired quote comparison is descriptive, "
        "not a fill estimate or verified exchange clearance. Never copy technical, price or restriction evidence between listings.")

def number(value):
    if isinstance(value,bool) or value is None:return None
    try:
        v=float(value)
        return v if isfinite(v) and 0<=v<=1e15 else None
    except (TypeError,ValueError,OverflowError):return None

def stamp(value):
    try:
        d=datetime.fromisoformat(value)
        return d if d.tzinfo is not None else None
    except (TypeError,ValueError):return None

def observation(instrument,candles=None):
    state=instrument.get("security_state","UNKNOWN")
    if state not in ("NORMAL","UNKNOWN",*SPECIAL):state="UNKNOWN"
    row={"id":instrument["id"],"exchange":instrument["exchange"],"isin":instrument["isin"],
         "symbol":instrument["symbol"],"security_state":state,"as_of":None,"close":None,"adjustment_status":None,
         "turnover_proxy_cr":None,"turnover_first_date":None,"quote":None}
    if candles and len(candles)>=21:
        row.update(as_of=candles[-1].date,close=candles[-1].close,adjustment_status=candles[-1].adjustment_status,
                   turnover_proxy_cr=round(median(c.close*c.volume for c in candles[-20:])/1e7,6),
                   turnover_first_date=candles[-20].date)
    observed,response=stamp(instrument.get("venue_quote_observed_at")),stamp(instrument.get("venue_quote_response_at"))
    price,spread,turnover=(number(instrument.get(k)) for k in ("venue_quote_price","venue_quote_spread_percent","venue_quote_turnover"))
    if observed and response and observed<=response and price is not None and price>0 and spread is not None and turnover is not None and turnover>0:
        row["quote"]={"observed_at":observed.isoformat(),"response_at":response.isoformat(),
            "price":price,"spread_percent":spread,"turnover_proxy_cr":turnover/1e7}
    return row

def collect(snapshot,instant):
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    groups=defaultdict(list)
    for section in snapshot.get("sections",[]):
        venue=section.get("section")
        if venue not in ("NSE","BSE") or section.get("status")!="READY":continue
        result=section.get("result") or {};coverage=result.get("discovery_coverage") or {}
        if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":continue
        try:
            expected=date.fromisoformat(coverage["expected_session"])
            if not 1<=(today-expected).days<=4:continue
        except (KeyError,TypeError,ValueError):continue
        rows=result.get("venue_observations")
        if not isinstance(rows,list) or len(rows)>20000:continue
        for row in rows:
            if (not isinstance(row,dict) or not exact_isin(row.get("isin")) or row.get("exchange")!=venue
                    or type(row.get("id")) is not int or row["id"]<=0 or not isinstance(row.get("symbol"),str)):continue
            if row.get("as_of") not in (None,expected.isoformat()):continue
            groups[row["isin"]].append(row)
    return groups

def fresh_quote(row,instant):
    q=row.get("quote")
    if not isinstance(q,dict):return None
    a,b=stamp(q.get("observed_at")),stamp(q.get("response_at"))
    if not a or not b or not instant-timedelta(minutes=15)<=a<=b<=instant:return None
    if a.astimezone(ZoneInfo("Asia/Kolkata")).date()!=instant.astimezone(ZoneInfo("Asia/Kolkata")).date():return None
    price,spread,turnover=(number(q.get(k)) for k in ("price","spread_percent","turnover_proxy_cr"))
    if price is None or price<=0 or spread is None or turnover is None or turnover<=0:return None
    return {**q,"price":price,"spread_percent":spread,"turnover_proxy_cr":turnover}

def consolidate(candidates,observations,instant,rank):
    """Prefer comparable liquidity evidence only among actual screen matches."""
    groups=defaultdict(list)
    for row in candidates:groups[row["isin"]].append(row)
    output=[]
    for isin,matches in groups.items():
        rows=observations.get(isin,[])
        # Reject conflicting registry observations instead of silently picking a ticker.
        by_venue={}
        conflict=False
        for row in rows:
            venue=row["exchange"]
            if venue in by_venue and by_venue[venue]!=row:conflict=True
            by_venue[venue]=row
        if len({(r["exchange"],r.get("id")) for r in matches})!=len(matches):conflict=True
        if len({r["exchange"] for r in matches})!=len(matches):conflict=True
        if conflict:continue
        # Old caches without detailed venue context can still show preliminary
        # matches; do not invent a liquidity comparison.
        valid=[r for r in matches if r.get("security_state") not in SPECIAL and
            (r["exchange"] not in by_venue or (by_venue[r["exchange"]]["id"]==r.get("id") and by_venue[r["exchange"]].get("security_state") not in SPECIAL))]
        if not valid:continue
        chosen=min(valid,key=rank)
        status="SCREEN_REPRESENTATIVE_ONLY"
        comparable=[by_venue[r["exchange"]] for r in valid if r["exchange"] in by_venue]
        preferred=None
        # Require both matching venues, same observed date and a fresh pair
        # taken no more than 60 seconds apart. Neither venue gets a default.
        if len(comparable)==2 and len({r.get("as_of") for r in comparable})==1 and comparable[0].get("as_of") is not None:
            a,b=comparable
            qa,qb=fresh_quote(a,instant),fresh_quote(b,instant)
            if qa and qb and abs((stamp(qa["observed_at"])-stamp(qb["observed_at"])).total_seconds())<=60:
                for first,second,x,y in ((a,b,qa,qb),(b,a,qb,qa)):
                    if x["spread_percent"]<y["spread_percent"] and x["turnover_proxy_cr"]>=y["turnover_proxy_cr"]:
                        preferred=first["exchange"];status="PAIRED_QUOTE_LIQUIDITY_PREFERENCE";break
                if preferred is None:status="PAIRED_QUOTE_NO_CLEAR_PREFERENCE"
            elif a.get("adjustment_status")==b.get("adjustment_status") and a.get("turnover_first_date") and a.get("turnover_first_date")==b.get("turnover_first_date"):
                x,y=number(a.get("turnover_proxy_cr")),number(b.get("turnover_proxy_cr"))
                if x is not None and y is not None and min(x,y)>0 and max(x,y)>=1.2*min(x,y):
                    preferred=a["exchange"] if x>y else b["exchange"]
                    status="HISTORICAL_TURNOVER_PREFERENCE"
        if preferred:
            chosen=next(r for r in valid if r["exchange"]==preferred)
        # Preserve other listing warnings even if the listing failed the screen.
        findings=sorted({"REPORTED_"+r["security_state"]+"_AT_"+r["exchange"] for r in rows if r.get("security_state") in SPECIAL}
            |{f for r in matches for f in (r.get("governance_review") or {}).get("findings",[])})
        context={"methodology":VERSION,"status":status,"preferred_exchange":preferred,
            "representative_exchange":chosen["exchange"],"observed_venues":sorted(set(by_venue)|{r["exchange"] for r in matches}),
            "screen_matching_venues":sorted(r["exchange"] for r in valid),
            "venue_observations":[{**r,"quote":fresh_quote(r,instant)} for r in sorted(rows,key=lambda x:x["exchange"])],
            "review_findings":findings,"execution_verified":False,"notice":NOTICE}
        output.append({**chosen,"company_venue_context":context})
    return output
