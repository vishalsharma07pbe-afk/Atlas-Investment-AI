"""Versioned, preliminary Elite research rubric. No probability or investment qualification.

Score comparable common inputs only; optional benchmark/quarterly/governance
evidence never gives one exchange an artificial scoring advantage.
"""
from math import isfinite

VERSION="ELITE-RESEARCH-RUBRIC-1"
WEIGHTS={"MOMENTUM_PATH":35,"REPORTED_EARNINGS":30,"UNDATED_RELATIVE_PE":15,"HISTORICAL_DOWNSIDE":20}
NOTICE=("Fixed illustrative research rubric, not a calibrated expected-return or confidence score. "
        "Weights and thresholds are engineering defaults, not backtested. Reported P/E is undated, "
        "earnings are not independently filing-verified, and historical price risk is not future or portfolio risk. "
        "Missing core inputs withhold the score; no renormalization. Final qualification remains withheld.")

def num(v,lo,hi):
    return type(v) in (float,int) and isfinite(v) and lo<=v<=hi

def scale(v,lo,hi):
    return max(0.,min(1.,(v-lo)/(hi-lo)))

def assess(row):
    w=(row.get("momentum_windows") or {}).get("60") or {}
    as_of=row.get("as_of")
    same_window=w.get("last_date")==as_of and bool(as_of) and w.get("adjustment_status")==row.get("adjustment_status") and row.get("adjustment_status") in ("ADJUSTED","RAW_UNADJUSTED")
    up=w.get("positive_day_percent")
    concentration=w.get("largest_gain_share_percent")
    gain=w.get("return_percent")
    dd=w.get("maximum_close_drawdown_percent")
    vol=w.get("annualized_daily_volatility_percent")
    profit=row.get("earnings_growth_percent")
    eps=row.get("eps_growth_percent")
    sales=row.get("sales_growth_percent")
    pe=row.get("reported_pe")
    sector=row.get("reported_sector_pe")
    factors={}
    if same_window and num(up,0,100) and num(concentration,0,100) and num(gain,-99.999,10000):
        # Reward breadth and dispersed gains more than the magnitude of return.
        factors["MOMENTUM_PATH"]=35*(.5*scale(up,50,75)+.3*(1-scale(concentration,5,25))+.2*scale(gain,0,25))
    if row.get("earnings_basis")=="UPSTOX_REPORTED_CONSOLIDATED_ANNUAL" and row.get("financial_period") and num(profit,10,100) and num(eps,10,100) and num(sales,5,10000):
        factors["REPORTED_EARNINGS"]=30*(.4*scale(profit,10,40)+.4*scale(eps,10,40)+.2*scale(sales,5,25))
    if row.get("ratio_period")=="UNVERIFIED" and num(pe,.000001,40) and num(sector,.000001,1e9):
        factors["UNDATED_RELATIVE_PE"]=15*(1-scale(pe/sector,.6,1.2))
    risk={"status":"UNAVAILABLE","historical_price_risk":None,"drawdown_percent":None,"volatility_percent":None,
          "as_of":as_of,"notice":"60 observed daily returns; illustrative bands, not calibrated risk, loss bounds or suitability."}
    if same_window and num(dd,0,100) and num(vol,0,10000):
        factors["HISTORICAL_DOWNSIDE"]=20*(.5*(1-scale(dd,5,25))+.5*(1-scale(vol,15,50)))
        # Use the worse band, not an average hiding one adverse metric.
        band="HIGH" if dd>=20 or vol>=40 else "MEDIUM" if dd>=10 or vol>=25 else "LOW"
        risk.update(status="OBSERVED_PRICE_RISK_ONLY",historical_price_risk=band,drawdown_percent=dd,volatility_percent=vol)
    components=[{"factor":k,"weight":weight,"points":round(factors[k],2) if k in factors else None} for k,weight in WEIGHTS.items()]
    missing=[k for k in WEIGHTS if k not in factors]
    # Report coverage as discrete domain statuses; this is not a probability.
    relative=row.get("benchmark_relative_strength") or {}
    quarter=row.get("quarterly_financials") or {}
    governance=row.get("governance_review") or {}
    domains=[
        {"domain":"PRICE_HISTORY","status":"PARTIAL" if same_window else "MISSING"},
        {"domain":"ANNUAL_EARNINGS","status":"PARTIAL" if "REPORTED_EARNINGS" in factors else "MISSING"},
        {"domain":"VALUATION","status":"PARTIAL" if "UNDATED_RELATIVE_PE" in factors else "MISSING"},
        {"domain":"QUARTERLY_EARNINGS","status":"PARTIAL" if quarter.get("items") else "MISSING"},
        {"domain":"BENCHMARK_ALIGNMENT","status":"OBSERVED" if relative.get("status")=="MATCHED_PRICE_INDEX_OBSERVATIONS" and relative.get("windows") else "MISSING"},
        {"domain":"GOVERNANCE","status":"PARTIAL" if governance.get("provider_security_state") not in (None,"UNKNOWN") or governance.get("ownership_status")=="COMPARABLE_QUARTERS" else "MISSING"},
        {"domain":"LIVE_EXECUTION","status":"MISSING"},
        {"domain":"PROSPECTIVE_VALIDATION","status":"MISSING"},
    ]
    blockers=sorted(set(governance.get("blockers") or [])|{
        "INDEPENDENT_DATED_FILING_VERIFICATION_REQUIRED","DATED_INTRINSIC_VALUATION_REQUIRED",
        "INDEPENDENT_ADJUSTMENT_AND_SESSION_VERIFICATION_REQUIRED","LIVE_SPREAD_AND_EXECUTION_LIQUIDITY_REQUIRED",
        "INDEPENDENT_PROSPECTIVE_STRATEGY_VALIDATION_REQUIRED","FINAL_QUALIFICATION_VALIDATION_REQUIRED"})
    return {"methodology":VERSION,"status":"PRELIMINARY_SCORE_ONLY" if not missing else "SCORE_WITHHELD",
            "score":round(sum(c["points"] for c in components),2) if not missing else None,
            "components":components,"missing_factors":missing,"historical_risk":risk,
            "evidence_coverage":{"domains":domains,"observed_count":sum(d["status"]=="OBSERVED" for d in domains),
                "partial_count":sum(d["status"]=="PARTIAL" for d in domains),"total_domains":len(domains),
                "status":"INCOMPLETE_EVIDENCE","probability":None},
            "blockers":blockers,"review_findings":list(governance.get("findings") or []),
            "qualified":False,"notice":NOTICE}
