"""Quarterly reported ownership percentages, not trade or pledge evidence.

Contract: https://upstox.com/developer/api-documentation/get-share-holdings/
The documented categories partition reported ownership; other_dii excludes
the separately reported mutual_funds category. Never infer trade volumes.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import calendar
import re

CATEGORIES=("promoters","fii","other_dii","mutual_funds","retail_and_other")
MONTHS={"Mar":3,"Jun":6,"Sep":9,"Dec":12}
NOTICE=("Provider-reported percentages of total shares; quarterly ownership changes "
        "are not proof of buying/selling, institutional intent, promoter pledges, "
        "or bulk/block deals. Corporate actions and denominator changes may affect percentages. "
        "Independent exchange filings remain unverified.")


def _quarter(label):
    if not isinstance(label,str):
        return None
    match=re.fullmatch(r"(Mar|Jun|Sep|Dec) (20[0-9]{2})",label)
    if not match:
        return None
    year,month=int(match[2]),MONTHS[match[1]]
    return date(year,month,calendar.monthrange(year,month)[1])


def _number(value):
    if type(value) not in (float,int):
        return None
    try:
        n=Decimal(str(value))
        return n if n.is_finite() and 0<=n<=100 else None
    except (ValueError,InvalidOperation):
        return None


def summarize(report,today):
    result={"status":"UNAVAILABLE","latest_period":None,"previous_period":None,
            "categories":[],"review_prompts":[],"notice":NOTICE,
            "blockers":["PROMOTER_PLEDGE_DATA_UNVERIFIED","BULK_BLOCK_DEAL_FEED_UNAVAILABLE",
                        "STOCK_LEVEL_TRANSACTION_DATA_UNVERIFIED"]}
    section=report.get("sections",{}).get("shareholding",{})
    if section.get("status")!="AVAILABLE" or not isinstance(section.get("data"),list):
        return result
    series={}
    for row in section["data"]:
        if not isinstance(row,dict):
            continue
        key=row.get("name")
        if key not in CATEGORIES:
            continue
        if key in series or not isinstance(row.get("history"),list):
            result["status"]="CONFLICTING_REPORTED_CATEGORIES"
            return result
        points={}
        for item in row["history"]:
            if not isinstance(item,dict):
                continue
            quarter=_quarter(item.get("period"))
            if quarter is None or quarter>today:
                continue
            value=_number(item.get("value"))
            if value is None or quarter in points:
                result["status"]="INVALID_OR_DUPLICATE_QUARTER"
                return result
            points[quarter]=value
        series[key]=points
    if not series or not any(series.values()):
        return result
    latest=max(q for points in series.values() for q in points)
    if (today-latest).days>150:
        result["status"]="STALE_QUARTER"
        return result
    result["latest_period"]=latest.isoformat()
    # No fallback to an older common quarter if the newest quarter is partial.
    if set(series)!=set(CATEGORIES) or any(latest not in points for points in series.values()):
        result["status"]="PARTIAL_LATEST_QUARTER"
        result["categories"]=[{"category":key,"latest_percent":float(points[latest]),
                               "previous_percent":None,"change_pp":None}
                              for key,points in series.items() if latest in points]
        return result
    def reconciled(q):
        return all(q in points for points in series.values()) and Decimal("99.5")<=sum(points[q] for points in series.values())<=Decimal("100.5")
    if not reconciled(latest):
        result["status"]="UNRECONCILED_LATEST_QUARTER"
        return result
    month=latest.month-3
    year=latest.year
    if month<=0:
        year-=1
        month+=12
    prior=date(year,month,calendar.monthrange(year,month)[1])
    comparable=reconciled(prior)
    result["previous_period"]=prior.isoformat() if comparable else None
    result["status"]="COMPARABLE_QUARTERS" if comparable else "LATEST_QUARTER_ONLY"
    for key in CATEGORIES:
        current=series[key][latest]
        before=series[key][prior] if comparable else None
        change=current-before if before is not None else None
        result["categories"].append({"category":key,"latest_percent":float(current),
                                    "previous_percent":float(before) if before is not None else None,
                                    "change_pp":float(change) if change is not None else None})
        # Conservative research prompt, not an inferred transaction or recommendation.
        if comparable and key in ("promoters","fii","other_dii","mutual_funds") and change<=Decimal("-1"):
            result["review_prompts"].append({"category":key,"change_pp":float(change),
                "reason":"REPORTED_OWNERSHIP_DECLINE_AT_LEAST_ONE_PP"})
    return result
