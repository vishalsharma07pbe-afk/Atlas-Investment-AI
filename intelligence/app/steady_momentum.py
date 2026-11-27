"""ATLAS steady-momentum research screen, independent of investment qualification.

No TradingView rating, execution promise or fabricated evidence. All thresholds
are versioned research heuristics. Read cached data only on dashboard requests.
"""
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta
from math import isfinite
from statistics import median
from zoneinfo import ZoneInfo
import json
from .replay_evidence import exact_isin
from .financial_strength import _block, _values, _recent_common
from .fundamental_quality import _ratio_rows

VERSION="STEADY-MOMENTUM-1"
NOTICE="ATLAS rule-based screen, not TradingView Strong Buy or investment qualification. Reported earnings and undated sector P/E are preliminary evidence. Historical turnover and AMFI six-month average capitalization are not live execution liquidity or current market cap. Thresholds not backtested. Coverage is limited to validated daily-history samples."

def numeric(v):
    return type(v) in (int,float) and isfinite(v)

def technical(candles,ind):
    if len(candles)<201:
        return None
    close=candles[-1].close
    r=[b.close/a.close-1 for a,b in zip(candles[-61:-1],candles[-60:])]
    if len(r)!=60 or not all(numeric(v) for v in r):
        return None
    up=sum(v>0 for v in r)
    down=sum(v<0 for v in r)
    ret20=close/candles[-21].close-1
    ret60=close/candles[-61].close-1
    ret200=close/candles[-201].close-1
    sma20,sma50,sma200,rsi,macd,signal,atr=(ind[k][-1] for k in ("sma_20","sma_50","sma_200","rsi_14","macd","macd_signal","atr_14"))
    turnover=median(c.close*c.volume for c in candles[-20:])
    if not all(numeric(v) for v in (sma20,sma50,sma200,rsi,macd,signal,atr,turnover)) or min(sma20,sma50,sma200)<=0:
        return None
    positive=sum(max(v,0) for v in r)
    concentration=max(r)/positive if positive>0 else 1
    if not (close>sma20>sma50>sma200 and 50<=rsi<=70 and macd>signal and 0<atr/close<=.05
            and .02<=ret20<=.25 and .05<=ret60<=.50 and 0<ret200<1
            and close/sma50<=1.18 and up>=33 and concentration<=.18
            and max(r)<.10 and min(r)>-.12 and turnover>=50_000_000 and candles[-1].volume>0):
        return None
    # For positive cumulative returns, negative information discreteness
    # indicates more positive than negative daily returns (FIP-inspired).
    return {"technical_rating":"ATLAS_STRONG_BULLISH","return_20_percent":round(ret20*100,2),
            "return_60_percent":round(ret60*100,2),"return_200_percent":round(ret200*100,2),
            "positive_day_percent":round(up/60*100,2),"information_discreteness":round((down-up)/60,4),
            "largest_up_day_percent":round(max(r)*100,2),"largest_gain_share_percent":round(concentration*100,2),
            "median_daily_turnover_cr":round(turnover/10_000_000,2),"rsi":round(rsi,2),
            "history_count":len(candles),"close":close,"adjustment_status":candles[-1].adjustment_status}

def fundamentals(report,today):
    income,_=_block(report,"income_statement")
    revenue=_values(income,"rows","revenue",today)
    profit=_values(income,"rows","net_profit",today)
    periods=_recent_common([revenue,profit],today)
    if len(periods)<3:
        return None,"MATCHED_ANNUAL_EARNINGS_MISSING"
    a,b,d=periods[-3:]
    if not (revenue[d]>revenue[b]>revenue[a]>0 and profit[d]>profit[b]>profit[a]>=25):
        return None,"EARNINGS_BASE_OR_CONSISTENCY"
    growth=(profit[d]/profit[b]-1)*100
    sales=(revenue[d]/revenue[b]-1)*100
    if not (10<=growth<=100 and sales>=5):
        return None,"EARNINGS_OR_SALES_GROWTH"
    # EPS currency/share basis is not independently verified. Require positive
    # reported EPS consistency as an additional filter, never derive fair value.
    eps=_values(income,"eps_rows","eps - diluted",today)
    if not eps:
        eps=_values(income,"eps_rows","eps - basic",today)
    if not all(k in eps for k in (a,b,d)):
        return None,"REPORTED_EPS_MISSING"
    if not (eps[d]>eps[b]>eps[a]>=1 and 10<=(eps[d]/eps[b]-1)*100<=100):
        return None,"EPS_BASE_OR_GROWTH"
    pe=_ratio_rows(report).get("PE")
    if not pe:
        return None,"REPORTED_PE_MISSING"
    if not (0<pe["company"]<=40 and pe["company"]<=1.2*pe["sector"]):
        return None,"VALUATION_SCREEN"
    return {"earnings_growth_percent":round(growth,2),"sales_growth_percent":round(sales,2),
            "eps_growth_percent":round((eps[d]/eps[b]-1)*100,2),"previous_profit_cr":profit[b],
            "profit_cr":profit[d],"financial_period":d,"reported_pe":pe["company"],
            "reported_sector_pe":pe["sector"],"ratio_period":"UNVERIFIED",
            "earnings_basis":"UPSTOX_REPORTED_CONSOLIDATED_ANNUAL"},None

def summarize(snapshot,connect,instant):
    from . import automatic_company_evidence, amfi_equity_caps
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    out={"methodology":VERSION,"status":"AWAITING_EVIDENCE","items":[],"reviewed_count":0,
         "technical_count":0,"sampled_count":0,"exclusions":[],"notice":NOTICE}
    if not snapshot.get("enabled"):
        out["status"]="DISABLED"
        return out
    if not automatic_company_evidence.permitted():
        out["status"]="AWAITING_EVIDENCE"
        out["exclusions"]=[{"reason":"COMPANY_EVIDENCE_NOT_AUTHORIZED","count":1}]
        return out
    caps=amfi_equity_caps.read(connect,today)
    excluded=Counter()
    candidates=[]
    with closing(connect()) as db:
        automatic_company_evidence._table(db)
        cached={r["isin"]:r["payload"] for r in db.execute(
            "SELECT isin,payload FROM automatic_company_evidence WHERE status IN ('AVAILABLE','PARTIAL') AND attempted_at BETWEEN ? AND ?",
            ((instant-timedelta(hours=24)).isoformat(),instant.isoformat()))}
    for section in snapshot.get("sections",[]):
        venue=section.get("section")
        if venue not in ("NSE","BSE") or section.get("status")!="READY":
            continue
        result=section.get("result") or {}
        out["sampled_count"]+=result.get("universe_size",0)
        coverage=result.get("discovery_coverage") or {}
        if coverage.get("calendar_checked_on")!=today.isoformat() or coverage.get("calendar_status")!="PUBLISHED_SESSION":
            continue
        for row in result.get("steady_momentum_candidates",[])[:200]:
            if row.get("exchange")!=venue or not exact_isin(row.get("isin")) or row.get("as_of")!=coverage.get("expected_session"):
                continue
            try:
                if not 1<=(today-date.fromisoformat(row["as_of"])).days<=4:
                    continue
            except (TypeError,ValueError):
                continue
            out["technical_count"]+=1
            isin=row["isin"]
            cap=caps.get(isin)
            if not cap:
                excluded["AMFI_CAP_EVIDENCE_MISSING"]+=1
                continue
            if cap["average_cap_cr"]<1000:
                excluded["LOW_AVERAGE_CAP"]+=1
                continue
            try:
                report=json.loads(cached.get(isin) or "{}")
                stamp=datetime.fromisoformat(report["retrieved_at"])
                if report.get("isin")!=isin or not instant-timedelta(hours=24)<=stamp<=instant:
                    raise ValueError()
                # Raw series need a reported action section before being used
                # in this screen; the screener already rejects known crossings.
                if row.get("adjustment_status")!="ADJUSTED" and not (report.get("sections",{}).get("corporate_actions",{}).get("status")=="AVAILABLE"):
                    excluded["RAW_ACTION_EVIDENCE_MISSING"]+=1
                    continue
                evidence,reason=fundamentals(report,today)
            except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
                excluded["COMPANY_EVIDENCE_MISSING"]+=1
                continue
            out["reviewed_count"]+=1
            if reason:
                excluded[reason]+=1
                continue
            candidates.append({**row,**evidence,**cap,"status":"SCREEN_MATCH_ONLY"})
    # Rank gradual positive-day consistency first, then turnover and growth.
    candidates.sort(key=lambda x:(-x["positive_day_percent"],x["largest_gain_share_percent"],
                                    -x["median_daily_turnover_cr"],-x["earnings_growth_percent"],x["isin"],x["exchange"]))
    seen=set()
    for row in candidates:
        if row["isin"] not in seen:
            seen.add(row["isin"])
            out["items"].append(row)
    out["matched_count"]=len(out["items"])
    out["items"]=out["items"][:10]
    out["exclusions"]=[{"reason":k,"count":v} for k,v in excluded.most_common()]
    out["status"]="SCREEN_MATCHES_AVAILABLE" if out["items"] else "NO_SCREEN_MATCHES" if out["technical_count"] else "AWAITING_EVIDENCE"
    return out
