"""Deterministic interpretation of the existing normalized company report.

No external requests. Annual comparisons use matched periods and units.
Provider ratios lack independently verified observation dates: compare them,
but never use them as a verified current fair-value or qualification input.
"""
from math import isfinite
import re

VERSION="FUNDAMENTAL-EVIDENCE-2"
ALIASES={
    "PE": {"p/e","pe","price to earnings","price earnings ratio","price to earnings ratio"},
    "PB": {"p/b","pb","price to book","price to book ratio"},
    "ROA": {"roa","return on assets"},
    "EV_EBITDA": {"ev/ebitda","enterprise value to ebitda"},
    "ROE": {"roe","return on equity"},
    "ROCE": {"roce","return on capital employed"},
    "DEBT_EQUITY": {"debt to equity","debt/equity","debt to equity ratio"},
    "INTEREST_COVERAGE": {"interest coverage","interest coverage ratio"},
}
REQUIRED_TRENDS=("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW","TOTAL_ASSETS","TOTAL_LIABILITIES")


def _number(value):
    return type(value) in (int,float) and isfinite(value)


def _name(value):
    return " ".join(re.sub(r"[-_]", " ", value.strip().lower()).split()) if isinstance(value,str) else ""


def _unit(value):
    # Do not assume conversions or currency when provider units differ.
    return " ".join(value.strip().casefold().split()) if isinstance(value,str) else ""


def _ratio_rows(report):
    block=report.get("sections",{}).get("ratios",{})
    rows=block.get("data") if block.get("status")=="AVAILABLE" else None
    result={}
    for key,names in ALIASES.items():
        matches=[r for r in (rows or []) if isinstance(r,dict) and _name(r.get("name")) in names]
        if len(matches)!=1:
            continue
        row=matches[0]
        expected="PERCENT" if key in ("ROA","ROE","ROCE") else "RATIO"
        a,b=row.get("company_value"),row.get("sector_value")
        # Source normalization supplies a separate sector unit on new records.
        # Legacy records cannot establish matching units for percentage ratios.
        if row.get("unit")!=expected or row.get("sector_unit")!=expected or not _number(a) or not _number(b):
            continue
        if key in ("PE","PB","EV_EBITDA") and (a<=0 or b<=0):
            continue
        if key in ("DEBT_EQUITY","INTEREST_COVERAGE") and (a<0 or b<0):
            continue
        relative=(a/b-1)*100 if key in ("PE","PB","EV_EBITDA") else None
        delta=a-b
        if not _number(delta) or (relative is not None and not _number(relative)):
            continue
        result[key]={"metric":key,"company":a,"sector":b,"unit":expected,
                     "difference":round(delta,4),
                     "premium_discount_percent":round(relative,4) if relative is not None else None,
                     "position":"ABOVE_SECTOR" if a>b else "BELOW_SECTOR" if a<b else "AT_SECTOR",
                     "observation_period":"UNVERIFIED","source":block.get("source")}
    return result


def _trends(report,year):
    rows=(report.get("financial_trends") or {}).get("items",[])
    valid={}
    for key in REQUIRED_TRENDS:
        matches=[r for r in rows if isinstance(r,dict) and r.get("metric")==key]
        if len(matches)!=1:
            continue
        r=matches[0]
        a,b=r.get("previous_year"),r.get("latest_year")
        if (type(a) is not int or type(b) is not int or not 2000<=a<b<=year or b-a!=1 or year-b>1
            or r.get("latest_period_may_be_stale") is not False or not _unit(r.get("unit"))
            or not _number(r.get("previous_value")) or not _number(r.get("latest_value"))):
            continue
        valid[key]=r
    return valid


def _matched_ratio(trends,numerator,denominator,metric,scale):
    a,b=trends.get(numerator),trends.get(denominator)
    if not a or not b or _unit(a["unit"])!=_unit(b["unit"]):
        return None
    if (a["previous_year"],a["latest_year"])!=(b["previous_year"],b["latest_year"]):
        return None
    if (a.get("previous_period"),a.get("latest_period"),a.get("statement_type"))!=(b.get("previous_period"),b.get("latest_period"),b.get("statement_type")):
        return None
    if b["previous_value"]<=0 or b["latest_value"]<=0:
        return None
    previous=a["previous_value"]/b["previous_value"]*scale
    latest=a["latest_value"]/b["latest_value"]*scale
    if not all(_number(v) for v in (previous,latest,latest-previous)):
        return None
    return {"metric":metric,"previous_year":a["previous_year"],"latest_year":a["latest_year"],
            "previous_period":a.get("previous_period"),"latest_period":a.get("latest_period"),
            "previous_value":round(previous,4),"latest_value":round(latest,4),
            "change":round(latest-previous,4),"unit":"PERCENT" if scale==100 else "RATIO",
            "source_metrics":[numerator,denominator],"sources":[a.get("source"),b.get("source")]}


def _four_year_series(row):
    """Only four consecutive, explicitly consolidated fiscal month-end periods."""
    if not row or row.get("statement_type")!="consolidated" or row.get("period_basis")!="DECLARED_ANNUAL_MONTH_END":
        return None
    points=row.get("annual_observations")
    if not isinstance(points,list) or not 4<=len(points)<=5:
        return None
    parsed=[]
    for point in points:
        if not isinstance(point,dict):
            return None
        period=point.get("period")
        value=point.get("value")
        if not isinstance(period,str) or not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",period) or not _number(value):
            return None
        parsed.append((period,value))
    if len({p for p,_ in parsed})!=len(parsed) or parsed!=sorted(parsed):
        return None
    parsed=parsed[-4:]
    if (any(int(b[0][:4])-int(a[0][:4])!=1 or a[0][5:]!=b[0][5:] for a,b in zip(parsed,parsed[1:]))
            or parsed[-1]!=(row.get("latest_period"),row["latest_value"])
            or parsed[-2]!=(row.get("previous_period"),row["previous_value"])):
        return None
    return parsed


def _multi_year(trends):
    series={k:points for k in ("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW")
            if (points:=_four_year_series(trends.get(k))) is not None}
    metrics=[]
    warnings=[]
    strengths=[]
    for key,points in series.items():
        values=[v for _,v in points]
        increases=sum(b>a for a,b in zip(values,values[1:]))
        decreases=sum(b<a for a,b in zip(values,values[1:]))
        nonpositive=sum(v<=0 for v in values)
        metrics.append({"metric":key,"unit":trends[key]["unit"],"observations":[{"period":p,"value":v} for p,v in points],
            "increasing_years":increases,"decreasing_years":decreases,
            "unchanged_years":3-increases-decreases,"nonpositive_years":nonpositive})
        if decreases>=2:
            warnings.append(key+"_MULTI_YEAR_DECLINES_REVIEW")
        if nonpositive:
            warnings.append(key+"_NONPOSITIVE_ANNUAL_OBSERVATION_REVIEW")
        if increases==3 and nonpositive==0:
            strengths.append(key+"_THREE_CONSECUTIVE_ANNUAL_INCREASES")
    cash=series.get("OPERATING_CASH_FLOW")
    profit=series.get("NET_PROFIT")
    conversion=None
    if (cash and profit and [p for p,_ in cash]==[p for p,_ in profit]
            and _unit(trends["OPERATING_CASH_FLOW"]["unit"])==_unit(trends["NET_PROFIT"]["unit"])
            and all(v>0 for _,v in profit)):
        total_cash=sum(v for _,v in cash)
        total_profit=sum(v for _,v in profit)
        if _number(total_cash) and _number(total_profit) and total_profit>0:
            ratio=total_cash/total_profit
            if _number(ratio):
                conversion={"first_period":profit[0][0],"last_period":profit[-1][0],
                            "cumulative_operating_cash":total_cash,"cumulative_net_profit":total_profit,
                            "unit":trends["NET_PROFIT"]["unit"],"cash_to_profit_ratio":round(ratio,4),
                            "negative_cash_years":sum(v<0 for _,v in cash)}
                if total_cash<total_profit:
                    warnings.append("CUMULATIVE_OPERATING_CASH_BELOW_NET_PROFIT_REVIEW")
    return {"status":"REPORTED_MULTI_YEAR_EVIDENCE" if metrics else "INSUFFICIENT_MATCHED_ANNUAL_HISTORY",
            "metrics":metrics,"cash_conversion":conversion,
            "missing_metrics":[k for k in ("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW") if k not in series],
            "warnings":warnings,"strengths":strengths,
            "notice":"Four consecutive reported consolidated annual periods; descriptive growth consistency and cumulative operating cash versus net profit. Not free cash flow, a universal sector-quality threshold, forecast or independently verified business rating."}


def summarize(report,year):
    trends=_trends(report,year)
    ratios=_ratio_rows(report)
    derived={}
    for num,den,key,scale in (
        ("NET_PROFIT","REVENUE","NET_MARGIN",100),
        ("OPERATING_PROFIT","REVENUE","OPERATING_MARGIN",100),
        ("OPERATING_CASH_FLOW","NET_PROFIT","OPERATING_CASH_TO_PROFIT",1),
        ("TOTAL_LIABILITIES","TOTAL_ASSETS","REPORTED_LIABILITIES_TO_ASSETS",100)):
        if key=="REPORTED_LIABILITIES_TO_ASSETS" and num in trends and any(trends[num][k]<0 for k in ("previous_value","latest_value")):
            continue
        row=_matched_ratio(trends,num,den,key,scale)
        if row:
            derived[key]=row
    warnings=[]
    strengths=[]
    for key in ("REVENUE","NET_PROFIT","OPERATING_PROFIT","OPERATING_CASH_FLOW"):
        row=trends.get(key)
        if row:
            if row["latest_value"]<0 or row["latest_value"]<row["previous_value"]:
                warnings.append(key+"_DETERIORATION_REVIEW")
            elif row["latest_value"]>0 and row["latest_value"]>row["previous_value"]:
                strengths.append(key+"_REPORTED_INCREASE")
    for key in ("NET_MARGIN","OPERATING_MARGIN","OPERATING_CASH_TO_PROFIT"):
        row=derived.get(key)
        if row and (row["latest_value"]<0 or row["change"]<0):
            warnings.append(key+"_DETERIORATION_REVIEW")
    multi_year=_multi_year(trends)
    warnings.extend(multi_year["warnings"])
    strengths.extend(multi_year["strengths"])
    # Financial institutions and industrial firms differ structurally. Do not
    # apply a universal cash-conversion, leverage or sector valuation threshold.
    valuation=[ratios[k] for k in ("PE","PB","EV_EBITDA") if k in ratios]
    gaps=["INDEPENDENT_FILING_VERIFICATION_REQUIRED","RATIO_OBSERVATION_PERIOD_UNVERIFIED",
          "INTRINSIC_VALUATION_INPUTS_UNVERIFIED","MARKET_SHARE_AND_PEER_RANK_UNVERIFIED"]
    gaps.extend("MISSING_"+k for k in REQUIRED_TRENDS if k not in trends)
    gaps.extend("MISSING_"+k for k in ALIASES if k not in ratios)
    gaps.extend("MISSING_"+k for k in ("NET_MARGIN","OPERATING_MARGIN","OPERATING_CASH_TO_PROFIT","REPORTED_LIABILITIES_TO_ASSETS") if k not in derived)
    return {"methodology":VERSION,"status":"REVIEW_REQUIRED" if warnings else "PARTIAL_EVIDENCE" if trends or ratios else "UNAVAILABLE",
            "strengths":strengths,"warnings":warnings,"multi_year_quality":multi_year,"derived_metrics":list(derived.values()),
            "sector_comparisons":list(ratios.values()),"valuation":{"status":"SECTOR_COMPARISON_ONLY" if valuation else "UNAVAILABLE",
              "comparisons":valuation,"fair_value":None,"scenario_status":"DATED_VALUATION_INPUTS_REQUIRED"},
            "gaps":gaps,
            "notice":"Reported annual trends and undated provider sector ratios are descriptive. Liability/assets is not debt/equity; operating cash/profit is not free cash flow. A premium or discount is not overvaluation or undervaluation. No intrinsic value, business-quality verdict or investment qualification."}
