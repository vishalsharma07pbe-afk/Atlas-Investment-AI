"""Historical business cash sensitivity, explicitly not intrinsic equity valuation.

Operating cash flow is not FCFF/FCFE. A normalized hypothetical distributable
cash amount and user-visible assumed growth/discount rates only illustrate the
effect of assumptions. No fair value, market-price target, or buy/sell gate.
"""
from datetime import datetime,timedelta
from math import isfinite
from .financial_strength import _block,_values,_recent_common

VERSION="VALUATION-SENSITIVITY-1"
NOTICE=("Historical consolidated provider-reported profit and operating cash, not audited free cash flow. "
        "Hypothetical cash retention, growth, discount and terminal rates are fixed engineering assumptions, "
        "not estimates or sector-specific costs of capital. The discounted amount is a mathematical cash-stream "
        "illustration, not enterprise/equity value or a price target. No margin of safety or recommendation.")
BLOCKERS=("INDEPENDENT_DATED_FORWARD_EARNINGS_REQUIRED","VERIFIED_CAPEX_AND_FREE_CASH_FLOW_REQUIRED",
          "VERIFIED_NET_DEBT_AND_SHARE_BASIS_REQUIRED","DATED_UNADJUSTED_PRICE_REQUIRED",
          "VALIDATED_DISCOUNT_RATE_AND_TERMINAL_ASSUMPTIONS_REQUIRED")
# Keep assumptions separate from historical observations; no fitted growth.
ASSUMPTIONS=(("STRESS",0.30,-5,16,0),("ILLUSTRATIVE",0.50,5,12,3),("OPTIMISTIC",0.70,10,10,4))

def pv(cash,growth,discount,terminal,years=5):
    if not all(type(x) in (float,int) and isfinite(x) for x in (cash,growth,discount,terminal)) or not 0<cash<=1e12 or not -0.5<=growth<=0.5 or not 0<discount<=0.5 or not 0<=terminal<discount or type(years) is not int or not 1<=years<=10:
        raise ValueError("INVALID_SCENARIO")
    flows=[cash*(1+growth)**i/(1+discount)**i for i in range(1,years+1)]
    terminal_pv=cash*(1+growth)**years*(1+terminal)/(discount-terminal)/(1+discount)**years
    total=sum(flows)+terminal_pv
    if not isfinite(total) or total>1e15:raise ValueError("SCENARIO_RANGE")
    return {"explicit_cash_stream_pv_cr":round(sum(flows),4),"terminal_stream_pv_cr":round(terminal_pv,4),
            "hypothetical_cash_stream_pv_cr":round(total,4),"terminal_share_percent":round(100*terminal_pv/total,4)}

def summarize(report,instant):
    from zoneinfo import ZoneInfo
    today=instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
    out={"methodology":VERSION,"status":"AWAITING_MATCHED_HISTORY","historical_periods":[],"scenarios":[],
        "intrinsic_value":None,"margin_of_safety_percent":None,"qualified":False,"blockers":list(BLOCKERS),"notice":NOTICE}
    try:
        stamp=datetime.fromisoformat(report["retrieved_at"])
        if stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant or report.get("historical_cache_only") is True:return out
        # Source identity/scope/units checked by the existing financial parser.
        income,inc_source=_block(report,"income_statement");cash,cf_source=_block(report,"cash_flow")
        if not income or not cash:return out
        if any(datetime.fromisoformat(source["retrieved_at"])!=stamp for source in (inc_source,cf_source)):return out
        profits=_values(income,"rows","net_profit",today)
        operating=_values(cash,"rows","operating",today)
        periods=_recent_common([profits,operating],today)
        if len(periods)<4:return out
        periods=periods[-4:]
        out["historical_periods"]=[{"period":p,"reported_net_profit_cr":profits[p],"reported_operating_cash_cr":operating[p]} for p in periods]
        # Show negative cash/profit but never capitalize a negative or mixed
        # four-year operating history; no survivorship-like cherry-picking.
        if any(profits[p]<=0 or operating[p]<=0 for p in periods):
            out["status"]="HISTORICAL_DETERIORATION_REVIEW";return out
        total_profit=sum(profits[p] for p in periods)
        total_cash=sum(operating[p] for p in periods)
        out["cash_conversion_ratio"]=round(total_cash/total_profit,4)
        # Lower of latest and four-year mean is a transparent historical anchor,
        # not normalized FCFE. No automatic sector eligibility.
        anchor=min(operating[periods[-1]],total_cash/4)
        out["operating_cash_anchor_cr"]=round(anchor,4)
        out["anchor_rule"]="LOWER_OF_LATEST_AND_FOUR_YEAR_MEAN_OPERATING_CASH"
        for name,retention,growth,discount,terminal in ASSUMPTIONS:
            stream=anchor*retention
            out["scenarios"].append({"case":name,"cash_fraction_percent":100*retention,"annual_growth_percent":growth,
                "discount_percent":discount,"terminal_growth_percent":terminal,"years":5,
                "hypothetical_start_cash_cr":round(stream,4),**pv(stream,growth/100,discount/100,terminal/100)})
        out["status"]="HYPOTHETICAL_CASH_STREAM_ONLY"
        return out
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,ZeroDivisionError):
        out.update(status="AWAITING_MATCHED_HISTORY",scenarios=[]);return out
