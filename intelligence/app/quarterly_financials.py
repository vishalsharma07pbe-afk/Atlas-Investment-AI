"""Dated provider-reported quarterly summaries. Never interpret annual detail as quarterly EPS."""
from calendar import monthrange
from datetime import date
from math import isfinite
import re

METRICS=("revenue","operating_profit","net_profit")
NOTICE=("Consolidated quarterly amounts in INR crore; exact period comparisons only. "
        "Negative or zero comparison bases have no percentage growth. "
        "Not independently reconciled to filings; quarterly EPS and valuation are not established.")
def period(label):
    m=re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (20[0-9]{2})",label) if isinstance(label,str) else None
    if not m:return None
    month=("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec").index(m[1])+1
    year=int(m[2])
    return date(year,month,monthrange(year,month)[1])
def shift(day,months):
    index=day.year*12+day.month-1+months
    year,month=divmod(index,12)
    return date(year,month+1,monthrange(year,month+1)[1])
def normalize(raw,today):
    if not isinstance(raw,dict) or raw.get("type")!="consolidated" or raw.get("time_period")!="quarterly" or raw.get("units_in")!="crore":return None
    rows=raw.get("income_statement")
    if not isinstance(rows,list) or not 1<=len(rows)<=40:return None
    series={}
    for row in rows:
        if not isinstance(row,dict):return None
        name=row.get("category")
        if name not in METRICS:continue
        points=row.get("history")
        if name in series or not isinstance(points,list) or not 1<=len(points)<=12:return None
        values={}
        for p in points:
            if not isinstance(p,dict):return None
            day=period(p.get("period"));v=p.get("value")
            if day is None or day>today or day in values or type(v) not in (int,float) or not isfinite(v) or abs(v)>1e12:return None
            values[day]=float(v)
        if len({d.month%3 for d in values})!=1:return None
        series[name]=[{"period":d.isoformat(),"value":v} for d,v in sorted(values.items())]
    return {"statement_type":"consolidated","time_period":"quarterly","units":"crore","series":series} if series else None
def growth(a,b):
    if a is None or b is None or b<=0 or a<0:return None
    v=100*(a/b-1)
    return round(v,4) if isfinite(v) and abs(v)<=1e12 else None
def summarize(report,today):
    result={"status":"UNAVAILABLE","latest_period":None,"items":[],"operating_margin_percent":None,
            "net_margin_percent":None,"notice":NOTICE,"quarterly_eps":None,"valuation_eligible":False}
    block=(report.get("sections") or {}).get("quarterly_income") or {}
    data=block.get("data");source=block.get("source")
    if block.get("status")!="AVAILABLE" or not isinstance(data,dict) or not isinstance(source,dict) or source.get("provider")!="UPSTOX" or source.get("endpoint")!=f"/v2/fundamentals/{report.get('isin')}/income-statement":return result
    if data.get("statement_type")!="consolidated" or data.get("time_period")!="quarterly" or data.get("units")!="crore":return result
    try:
        series={}
        for key,rows in data["series"].items():
            if key not in METRICS or not isinstance(rows,list) or not 1<=len(rows)<=12:return result
            points={}
            for row in rows:
                d=date.fromisoformat(row["period"]);v=row["value"]
                if d>today or d.day!=monthrange(d.year,d.month)[1] or d in points or type(v) not in (int,float) or not isfinite(v) or abs(v)>1e12:return result
                points[d]=v
            if len({d.month%3 for d in points})!=1:return result
            series[key]=points
        latest=max(d for p in series.values() for d in p)
        if (today-latest).days>150:
            result["status"]="STALE_QUARTER";return result
        result["latest_period"]=latest.isoformat()
        if any(latest not in series.get(k,{}) for k in METRICS):
            result["status"]="PARTIAL_LATEST_QUARTER"
        else:result["status"]="REPORTED_QUARTERLY_COMPARISONS"
        for key in METRICS:
            p=series.get(key,{})
            if latest not in p:continue
            current=p[latest];prev=p.get(shift(latest,-3))
            yoy=growth(current,p.get(shift(latest,-12)))
            prior_yoy=growth(prev,p.get(shift(latest,-15)))
            result["items"].append({"metric":key,"latest_value":current,
                "previous_quarter_growth_percent":growth(current,prev),"year_over_year_growth_percent":yoy,
                "prior_year_over_year_growth_percent":prior_yoy,
                "growth_acceleration_pp":round(yoy-prior_yoy,4) if yoy is not None and prior_yoy is not None else None})
        revenue=series.get("revenue",{}).get(latest)
        if revenue is not None and revenue>0:
            for metric,field in (("operating_profit","operating_margin_percent"),("net_profit","net_margin_percent")):
                val=series.get(metric,{}).get(latest)
                if val is not None:
                    margin=100*val/revenue
                    if isfinite(margin) and abs(margin)<=1e12:result[field]=round(margin,4)
        return result
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError,ZeroDivisionError):
        return {"status":"UNAVAILABLE","latest_period":None,"items":[],"operating_margin_percent":None,
            "net_margin_percent":None,"notice":NOTICE,"quarterly_eps":None,"valuation_eligible":False}
