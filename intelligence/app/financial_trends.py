"""Annual statement comparisons from normalized company evidence.

Provider contract: consolidated yearly summaries use month/year labels
(e.g. Mar 2025). Preserve period identity; retrieval time is not publication time.
Legacy year-only labels are retained for compatibility, not assumed to be March.
"""
from calendar import monthrange
from datetime import date
from math import isfinite
import re

METRICS = {
    "REVENUE": ("income_statement", {"revenue", "total revenue", "revenue from operations", "net sales"}),
    "NET_PROFIT": ("income_statement", {"net profit", "net income", "profit after tax", "net profit after tax"}),
    "OPERATING_PROFIT": ("income_statement", {"operating profit"}),
    "OPERATING_CASH_FLOW": ("cash_flow", {"operating", "cash flow from operations", "cash flow from operating activities", "net cash from operating activities", "net cash flow from operating activities", "operating cash flow"}),
    "TOTAL_ASSETS": ("balance_sheet", {"total_asset"}),
    "TOTAL_LIABILITIES": ("balance_sheet", {"total_liability"}),
}
MONTHS={name.lower():i for i,name in enumerate(("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"),1)}
NOTICE = ("Consolidated yearly provider summaries, not independently reconciled with filings. "
          "Changes describe reported history, not forecasts, valuation or investment advice.")


def _period(value, as_of, declared_annual):
    if not isinstance(value,str):
        return None
    match=re.fullmatch(r"(?:FY\s*)?(20\d{2})",value.strip(),re.I)
    if match:
        year=int(match[1])
        return (year,0) if year<=as_of.year else None
    match=re.fullmatch(r"([A-Za-z]{3})\s+(20\d{2})",value.strip())
    if match and declared_annual:
        year=int(match[2])
        month=MONTHS.get(match[1].lower())
        if month and date(year,month,monthrange(year,month)[1])<=as_of:
            return year,month
    return None


def _number(value):
    return type(value) in (int,float) and isfinite(value)


def _label(period):
    year,month=period
    return f"{year:04d}-{month:02d}" if month else f"FY{year}"


def _series(rows,as_of,declared_annual):
    if not isinstance(rows,list) or not 2<=len(rows)<=5:
        return None
    points={}
    for point in rows:
        if not isinstance(point,dict):
            return None
        period,value=_period(point.get("period"),as_of,declared_annual),point.get("value")
        if period is None or period in points or not _number(value):
            return None
        points[period]=float(value)
    periods=sorted(points)
    # A fiscal year-end change or multiple quarters cannot be treated as annual growth.
    if len({p[1] for p in periods})!=1 or periods[-1][0]-periods[-2][0]!=1:
        return None
    return [(p,points[p]) for p in periods]


def summarize(report,latest_year,*,as_of=None):
    as_of=as_of or date(latest_year,12,31)
    sections=report.get("sections",{})
    items,missing=[],[]
    for key,(section,aliases) in METRICS.items():
        block=sections.get(section,{})
        data=block.get("data") or {}
        unit=data.get("units")
        rows=data.get("rows") or []
        scope,frequency=data.get("statement_type"),data.get("time_period")
        declared=scope=="consolidated" and frequency=="yearly"
        # Legacy cache without scope is accepted only for legacy year-only labels.
        compatible=scope in (None,"consolidated") and frequency in (None,"yearly")
        points=None
        if compatible and block.get("status")=="AVAILABLE" and isinstance(unit,str) and unit.strip():
            if section=="balance_sheet":
                field=next(iter(aliases))
                points=_series([{"period":p.get("period"),"value":p.get(field)} for p in rows],as_of,declared)
            else:
                matching=[r for r in rows if isinstance(r.get("name"),str)
                          and " ".join(r["name"].lower().replace("_"," ").split()) in aliases]
                if len(matching)==1:
                    points=_series(matching[0].get("history"),as_of,declared)
        if not points:
            missing.append(key)
            continue
        (prior,previous),(period,value)=points[-2:]
        change=value-previous
        if not isfinite(change):
            missing.append(key)
            continue
        percent=100*(change/previous) if previous>0 and value>=0 else None
        if percent is not None and not isfinite(percent):
            percent=None
        direction="INCREASED" if change>0 else "DECREASED" if change<0 else "UNCHANGED"
        # Three-year growth requires four consecutive observations and positive bases.
        cagr=None
        if len(points)>=4:
            sample=points[-4:]
            if all(b[0][0]-a[0][0]==1 for a,b in zip(sample,sample[1:])) and all(v>0 for _,v in sample):
                growth=100*((sample[-1][1]/sample[0][1])**(1/3)-1)
                if isfinite(growth):
                    cagr=round(growth,4)
        items.append({"metric":key,"section":section,"unit":unit,
                      "previous_year":prior[0],"latest_year":period[0],
                      "previous_period":_label(prior),"latest_period":_label(period),
                      "period_basis":"DECLARED_ANNUAL_MONTH_END" if period[1] else "YEAR_LABEL_ONLY",
                      "statement_type":scope,"previous_value":previous,"latest_value":value,
                      "change":round(change,6),"change_percent":round(percent,4) if percent is not None else None,
                      "cagr_3y_percent":cagr,"direction":direction,"source":block.get("source"),
                      "latest_period_may_be_stale":((as_of.year-period[0])*12+as_of.month-period[1]>18) if period[1] else latest_year-period[0]>1})
    return {"status":"PARTIAL" if items and missing else "AVAILABLE" if items else "UNAVAILABLE",
            "items":items,"missing_metrics":missing,"notice":NOTICE}
