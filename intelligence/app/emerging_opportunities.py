"""Early business/price convergence, independent of strict FIP qualification.

Fixed research proxies using current completed adjusted sessions and exact
consolidated provider quarters. No return estimates, no speculative catalysts.
"""
from datetime import date,datetime,timedelta
from math import isfinite

VERSION="EMERGING-RESEARCH-1"
NOTICE="Bounded early-stage research signals; not a forecast, confirmed accumulation, or an entry recommendation. Missing business evidence stays unassessed."
def num(x,a,b):return type(x) in (int,float) and isfinite(x) and a<=x<=b
def obj(x):return x if isinstance(x,dict) else {}

def price_setup(f):
    if f.get("adjustment_status")!="ADJUSTED" or f.get("calendar_matched") is not True or f.get("observations")!=253:return False
    if not all(num(f.get(k),a,b) for k,a,b in (("return_252_percent",0,70),("return_60_percent",-5,20),("max_daily_gain_20_percent",0,9.99),("turnover_cr",5,1e12),("near_annual_high_percent",70,98))):return False
    p=obj(f.get("professional_patterns"));c=obj(p.get("contraction_checks"))
    old,mid,recent,vol=(c.get(k) for k in ("older_range_percent","middle_range_percent","recent_range_percent","recent_to_prior_volume"))
    return (f.get("above_sma200") is True and all(num(v,.00001,1000) for v in (old,mid,recent)) and num(vol,0,.85)
        and mid<=old*.85 and recent<=mid*.85 and c.get("pivot_confirmed") is False)

def assess(row,f,report,today):
    if not price_setup(f):return None
    result={"methodology":VERSION,"isin":row["isin"],"id":row["id"],"exchange":row["exchange"],"symbol":row["symbol"],"as_of":row["as_of"],
        "state":"PRICE_SETUP_AWAITING_BUSINESS_EVIDENCE","signals":["CONTRACTING_RANGE_AND_VOLUME"],"qualified":False}
    if report.get("isin")!=row["isin"]:return result
    q=obj(report.get("quarterly_financials"))
    try:
        period=date.fromisoformat(q["latest_period"])
        if not 0<=(today-period).days<=150:return result
    except (KeyError,TypeError,ValueError):return result
    by={}
    for item in q.get("items",[]):
        if not isinstance(item,dict):continue
        k=item.get("metric")
        if k in by:return result
        by[k]=item
    rev,profit=by.get("revenue",{}),by.get("net_profit",{})
    rg,pg=rev.get("year_over_year_growth_percent"),profit.get("year_over_year_growth_percent")
    ra,pa=rev.get("growth_acceleration_pp"),profit.get("growth_acceleration_pp")
    if not all(num(v,-100,1000) for v in (rg,pg,ra,pa)):return result
    result["quarter"]=period.isoformat()
    result["observed_growth"]={"revenue_yoy_percent":rg,"profit_yoy_percent":pg,"revenue_acceleration_pp":ra,"profit_acceleration_pp":pa}
    if min(rg,pg)<=0 or min(ra,pa)<0:
        result["state"]="BUSINESS_TREND_CAUTION";return result
    if rg>=8 and pg>=10 and min(ra,pa)>=2:
        result["signals"].append("JOINT_EARNINGS_ACCELERATION")
        if pg-rg>=5:result["signals"].append("PROFIT_GROWTH_EXCEEDS_REVENUE")
        result["state"]="EARLY_CONVERGENCE_RESEARCH"
    else:result["state"]="PRICE_SETUP_BUSINESS_CONFIRMATION_PENDING"
    return result

def recovery_order(snapshot,today):
    """Existing public sample only, for the ordinary company worker's due queue."""
    from . import multi_strategy
    if snapshot.get("scope")!="PUBLIC_MARKET_RESEARCH_ONLY":return set()
    return {r["isin"] for r in multi_strategy.current_rows(snapshot,today) if price_setup(r["multi_strategy_price"])}
