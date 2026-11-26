"""Same-scope annual cash and liquidity evidence, not a solvency rating.

Use documented Upstox INR crore categories and detailed line items only.
No capital-expenditure inference, forecasting, or qualification promotion.
"""
from math import isfinite
import re
from .financial_trends import _series, _label

DETAIL_NAMES={
    "balance_sheet":{"current assets","current liabilities","net current asset"},
    "cash_flow":{"total cash flow","cash (start of the year)","cash (end of the year)"},
}
LIMIT=1e12
NOTICE=("Provider-reported consolidated annual amounts in INR crore. "
        "Working capital and current ratio are descriptive, not a sector-independent solvency verdict. "
        "Cash flow sum and cash balance differences are reconciliation observations, not filing verification. "
        "Investing cash flow is not capital expenditure; free cash flow and debt service coverage are not inferred.")

def _block(report,key):
    block=(report.get("sections") or {}).get(key) or {}
    data=block.get("data")
    if (block.get("status")!="AVAILABLE" or not isinstance(data,dict)
        or data.get("statement_type")!="consolidated" or data.get("time_period")!="yearly"
        or str(data.get("units","")).strip().casefold() not in ("crore","inr crore")):
        return {},None
    source=block.get("source")
    isin=report.get("isin")
    if (not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin)
        or not isinstance(source,dict) or source.get("provider")!="UPSTOX"
        or source.get("endpoint")!=f"/v2/fundamentals/{isin}/"+key.replace("_","-")):
        return {},None
    return data,source

def _values(data,field,name,today):
    rows=data.get(field)
    if not isinstance(rows,list) or len(rows)>40:
        return {}
    matches=[r for r in rows if isinstance(r,dict) and isinstance(r.get("name"),str)
             and r["name"].strip().casefold()==name]
    if len(matches)!=1:
        return {}
    points=_series(matches[0].get("history"),today,True)
    if not points or any(p[1]==0 or abs(v)>LIMIT for p,v in points):
        return {}
    return {_label(p):v for p,v in points}

def _recent_common(series,today):
    if any(not values for values in series):
        return []
    periods=sorted(set.intersection(*(set(v) for v in series)))
    # Only contiguous comparable annual periods, same fiscal year end, latest within 18 months.
    if len(periods)<2 or any(b[:4]!=str(int(a[:4])+1) or a[5:]!=b[5:] for a,b in zip(periods,periods[1:])):
        return []
    last=periods[-1]
    if (today.year-int(last[:4]))*12+today.month-int(last[5:])>18:
        return []
    # Never call older common data the latest if one required series is newer.
    if any(max(v)!=last for v in series):
        return []
    return periods

def _rounded(v):
    return round(v,4) if isfinite(v) and abs(v)<=LIMIT else None

def summarize(report,today):
    balance,bs_source=_block(report,"balance_sheet")
    cash,cf_source=_block(report,"cash_flow")
    assets=_values(balance,"detail_rows","current assets",today)
    liabilities=_values(balance,"detail_rows","current liabilities",today)
    net=_values(balance,"detail_rows","net current asset",today)
    liquidity=[]
    for period in _recent_common([assets,liabilities],today):
        a,l=assets[period],liabilities[period]
        if a<0 or l<=0:
            liquidity=[]
            break
        ratio=_rounded(a/l)
        if ratio is None:
            liquidity=[]
            break
        working=a-l
        liquidity.append({"period":period,"current_assets":a,"current_liabilities":l,
                          "current_ratio":ratio,"working_capital":_rounded(working),
                          "reported_net_current_asset":net.get(period),
                          "net_current_asset_difference":_rounded(working-net[period]) if period in net else None})
    operating=_values(cash,"rows","operating",today)
    investing=_values(cash,"rows","investing",today)
    financing=_values(cash,"rows","financing",today)
    total=_values(cash,"detail_rows","total cash flow",today)
    opening=_values(cash,"detail_rows","cash (start of the year)",today)
    closing=_values(cash,"detail_rows","cash (end of the year)",today)
    flows=[]
    for period in _recent_common([operating,investing,financing],today):
        combined=operating[period]+investing[period]+financing[period]
        if _rounded(combined) is None:
            flows=[]
            break
        start,end=opening.get(period),closing.get(period)
        movement=_rounded(end-start) if start is not None and end is not None and start>=0 and end>=0 else None
        flows.append({"period":period,"operating":operating[period],"investing":investing[period],
                      "financing":financing[period],"combined_cash_flows":_rounded(combined),
                      "reported_total_cash_flow":total.get(period),
                      "total_cash_flow_difference":_rounded(combined-total[period]) if period in total else None,
                      "opening_cash":start if start is not None and start>=0 else None,
                      "closing_cash":end if end is not None and end>=0 else None,
                      "cash_balance_movement":movement,
                      "balance_movement_difference":_rounded(movement-combined) if movement is not None else None})
    return {"status":"REPORTED_ANNUAL_FINANCIAL_STRENGTH" if liquidity or flows else "INSUFFICIENT_MATCHED_EVIDENCE",
            "unit":"INR_CRORE","liquidity":liquidity,"cash_flows":flows,
            "liquidity_source":bs_source if liquidity else None,"cash_flow_source":cf_source if flows else None,
            "free_cash_flow":None,"solvency_rating":None,"notice":NOTICE}
