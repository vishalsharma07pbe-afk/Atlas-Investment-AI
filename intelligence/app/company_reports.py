"""One bounded public company report per exact ISIN. No private data or provider requests."""
from collections import defaultdict
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from .replay_evidence import exact_isin
from . import company_venues

HORIZONS=("SWING","SHORT_TERM","LONG_TERM")
NOTICE="Shared reported company evidence and exact dated venue/horizon observations. No transfer of price levels, replay or execution clearance between venues. Current sampled research only; not a full registry or a qualified recommendation."

def entries(snapshot):
    if not snapshot.get("enabled") or snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return
    try:today=date.fromisoformat(snapshot["research_date"])
    except (ValueError,TypeError,KeyError):return
    def valid(row):
        if not isinstance(row,dict) or not exact_isin(row.get("isin")) or row.get("exchange") not in ("NSE","BSE") or type(row.get("id")) is not int or row["id"]<=0:return False
        try:return 1<=(today-date.fromisoformat(row["as_of"])).days<=4
        except (ValueError,TypeError,KeyError):return False
    for section in snapshot.get("sections",[]):
        if section.get("section") not in ("NSE","BSE") or section.get("status")!="READY":continue
        result=section.get("result") or {}
        coverage=result.get("discovery_coverage") or {}
        if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":continue
        for horizon in HORIZONS:
            group=(result.get("horizons") or {}).get(horizon) or {}
            if group.get("status")!="TECHNICAL_WATCH_ONLY":continue
            for row in group.get("candidates",[])[:5]:
                if valid(row) and row["exchange"]==section["section"] and row["as_of"]==coverage.get("expected_session"):yield horizon,row
    screen=snapshot.get("steady_momentum") or {}
    lists=[screen.get("items",[])]+[screen.get("category_items",{}).get(k,[]) for k in ("LARGE_CAP","MID_CAP","SMALL_CAP")]
    for rows in lists:
        for row in rows[:10]:
            if valid(row) and row.get("status")=="SCREEN_MATCH_ONLY":yield "ELITE",row

def grouped(snapshot):
    groups=defaultdict(list)
    for horizon,row in entries(snapshot):groups[row["isin"]].append((horizon,row))
    return groups

def attach(snapshot,instant):
    reports={}
    venues=company_venues.collect(snapshot,instant)
    for isin,items in grouped(snapshot).items():
        observations={}
        conflict=False
        company=[]
        reviews=[]
        news=[]
        pledges=[]
        financial=[]
        comparative={}
        official={}
        findings=set()
        for horizon,row in items:
            key=(horizon,row["exchange"],row["id"],row["as_of"])
            ref={k:row.get(k) for k in ("id","symbol","exchange","as_of","close","adjustment_status","history_count","security_state")}
            ref["horizon"]=horizon
            ref["qualification_status"]=(row.get("stock_qualification") or {}).get("status",row.get("status","WATCH_ONLY"))
            if key in observations and observations[key]!=ref:conflict=True
            observations[key]=ref
            for block in ("stock_qualification","selection_company_context","company_venue_context"):
                findings.update(v for v in (row.get(block) or {}).get("review_findings",[]) if isinstance(v,str))
            evidence=row.get("company_evidence") or {}
            try:
                captured=datetime.fromisoformat(evidence["retrieved_at"])
                if evidence.get("isin")==isin and captured.tzinfo and instant-timedelta(hours=24)<=captured<=instant:
                    company.append(evidence)
            except (TypeError,ValueError,KeyError):pass
            pledge=row.get("independent_pledge_evidence") or {}
            if pledge.get("isin")==isin and pledge.get("status")=="REPORTED_QUARTERLY_AGGREGATE":
                pledges.append(pledge)
                if pledge.get("total_encumbered_shares",0)>0:findings.add("ISSUER_REPORTED_PROMOTER_ENCUMBRANCE_REVIEW")
            relative=row.get("sector_price_context") or {}
            if relative.get("isin")==isin and relative.get("exchange")==row["exchange"] and relative.get("id")==row["id"] and relative.get("as_of")==row["as_of"]:
                k=(row["exchange"],row["id"],row["as_of"])
                if k in comparative and comparative[k]!=relative:
                    findings.add("CONFLICTING_SECTOR_PRICE_EVIDENCE")
                    comparative[k]=None
                elif k not in comparative:comparative[k]=relative
            index=row.get("official_sector_benchmark") or {}
            if index.get("isin")==isin and index.get("exchange")==row["exchange"] and index.get("id")==row["id"] and index.get("as_of")==row["as_of"]:
                key=(row["exchange"],row["id"],row["as_of"])
                if key in official and official[key]!=index:
                    findings.add("CONFLICTING_OFFICIAL_SECTOR_BENCHMARK")
                    official[key]=None
                elif key not in official:official[key]=index
            filing=row.get("independent_financial_evidence") or {}
            if filing.get("isin")==isin and filing.get("status")=="REPORTED_CONSOLIDATED_FILING":
                financial.append(filing)
                findings.update((row.get("governance_review") or {}).get("findings",[]))
            headline=row.get("news_evidence") or {}
            if headline.get("isin")==isin and headline.get("source_instrument_key")=="NSE_EQ|"+isin:
                try:
                    captured=datetime.fromisoformat(headline["retrieved_at"])
                    if captured.tzinfo and instant-timedelta(hours=2)<=captured<=instant:news.append(headline)
                except (TypeError,ValueError,KeyError):pass
            review=row.get("ai_review") or {}
            if review.get("company_isin")==isin:reviews.append(review)
        # Same capture must carry the same source sections. Prefer the enriched
        # representation (peer context) without mixing different captures.
        shared=None
        if company:
            latest=max(datetime.fromisoformat(r["retrieved_at"]) for r in company)
            current=[r for r in company if datetime.fromisoformat(r["retrieved_at"])==latest]
            if all(r.get("sections")==current[0].get("sections") for r in current):
                shared=max(current,key=lambda r:len(r))
            else:findings.add("CONFLICTING_COMPANY_SOURCE_CAPTURE")
        review=reviews[0] if reviews and all(r==reviews[0] for r in reviews) else None
        if conflict:
            findings.add("CONFLICTING_LISTING_OBSERVATIONS")
            continue
        other=venues.get(isin,[])
        findings.update("REPORTED_"+r["security_state"]+"_AT_"+r["exchange"] for r in other if r.get("security_state") in company_venues.SPECIAL)
        findings.update(f for r in other for f in (r.get("exchange_surveillance") or {}).get("findings",[]))
        shared_news=news[0] if news and all(r==news[0] for r in news) else None
        if news and shared_news is None:findings.add("CONFLICTING_COMPANY_NEWS_CAPTURE")
        shared_pledge=pledges[0] if pledges and all(p==pledges[0] for p in pledges) else None
        if pledges and shared_pledge is None:findings.add("CONFLICTING_PLEDGE_FILING_EVIDENCE")
        # Cross-source comparison can differ by view availability; reconcile
        # the source capture independently of supplementary provider context.
        source=[{k:v for k,v in r.items() if k!="comparison"} for r in financial]
        shared_financial=None
        if source and all(r==source[0] for r in source):
            shared_financial={**source[0]}
            from .nse_financial_filings import compare
            shared_financial["comparison"]=compare(shared_financial,shared)
        elif source:findings.add("CONFLICTING_FINANCIAL_FILING_EVIDENCE")
        reports[isin]={"isin":isin,"status":"REVIEW_REQUIRED" if findings else "RESEARCH_ONLY",
            "observations":[observations[k] for k in sorted(observations)],
            "observed_venues":sorted({r["exchange"] for r in observations.values()}|{r["exchange"] for r in other}),
            "venue_observations":[{**r,"quote":company_venues.fresh_quote(r,instant)} for r in sorted(other,key=lambda r:(r["exchange"],r["id"]))],
            "review_findings":sorted(findings),"company_evidence":shared,"news_evidence":shared_news,"independent_pledge_evidence":shared_pledge,"independent_financial_evidence":shared_financial,"sector_price_context":[comparative[k] for k in sorted(comparative) if comparative[k] is not None],"official_sector_benchmarks":[official[k] for k in sorted(official) if official[k] is not None],"ai_review":review,
            "qualified":False,"notice":NOTICE}
    snapshot["company_reports"]={"status":"AVAILABLE" if reports else "AWAITING_EVIDENCE","items":reports,"notice":NOTICE}
    return snapshot
