"""Read-only risk statistics from strictly dated, user-supplied mutual fund NAVs."""
from datetime import date
from decimal import Decimal
from math import sqrt
from statistics import stdev
from pydantic import BaseModel,Field,model_validator

class DatedNav(BaseModel):
    as_of:date
    nav:Decimal=Field(gt=0,allow_inf_nan=False)

class HistoricalRiskRequest(BaseModel):
    scheme_code:str=Field(pattern=r"^[0-9]{1,12}$")
    source_name:str=Field(min_length=1,max_length=120)
    observations:list[DatedNav]=Field(min_length=2,max_length=4000)
    @model_validator(mode="after")
    def dates_valid(self):
        dates=[x.as_of for x in self.observations]
        if any(d>date.today() for d in dates):raise ValueError("Future NAV date")
        if any(b<=a for a,b in zip(dates,dates[1:])):raise ValueError("NAV dates must increase strictly")
        return self

def historical_risk(request:HistoricalRiskRequest)->dict:
    points=request.observations
    changes=[float(b.nav/a.nav-Decimal(1)) for a,b in zip(points,points[1:])]
    intervals=[(b.as_of-a.as_of).days for a,b in zip(points,points[1:])]
    peak=points[0].nav
    max_drawdown=Decimal(0)
    for point in points:
        peak=max(peak,point.nav)
        drawdown=point.nav/peak-Decimal(1)
        max_drawdown=min(max_drawdown,drawdown)
    days=(points[-1].as_of-points[0].as_of).days
    cumulative=points[-1].nav/points[0].nav-Decimal(1)
    annualized=(float(points[-1].nav/points[0].nav)**(365.25/days)-1)*100
    # Volatility is intentionally unavailable when NAV intervals are not all one
    # calendar day; unequal spacing must not be treated as equal daily returns.
    regular=all(delta==1 for delta in intervals)
    volatility=stdev(changes)*sqrt(365)*100 if regular and len(changes)>=2 else None
    return {
        "scheme_code":request.scheme_code,"source_name":request.source_name,
        "source_verification":"USER_SUPPLIED_UNVERIFIED",
        "first_date":str(points[0].as_of),"last_date":str(points[-1].as_of),
        "observations":len(points),"elapsed_days":days,
        "cumulative_return_pct":round(float(cumulative)*100,4),
        "annualized_return_pct":round(annualized,4),
        "maximum_drawdown_pct":round(float(max_drawdown)*100,4),
        "annualized_volatility_pct":round(volatility,4) if volatility is not None else None,
        "volatility_status":"AVAILABLE_CALENDAR_DAILY" if volatility is not None else "UNAVAILABLE_IRREGULAR_OR_INSUFFICIENT",
        "notice":"NAV-only historical price returns, not total investor returns. Daily volatility requires consecutive calendar-day observations (unusual for mutual funds); missing or irregular dates are never filled or annualized as if daily. Past performance does not predict future returns.",
        "stored":False}
