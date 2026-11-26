"""Reported annual earnings bridges; no share-basis or valuation inference."""
from .financial_strength import _block, _values, _recent_common, _rounded

INCOME_NAMES={"revenue","other income","total revenue","total expenses","profit before tax","tax","profit after tax"}
NOTICE=("Provider-reported consolidated annual INR crore amounts, matched by fiscal period. "
        "Arithmetic differences may reflect rounding, accounting adjustments or reporting scope; not evidence of fraud. "
        "Other income is not necessarily nonrecurring. Tax/profit is descriptive, not a statutory tax rate. "
        "Detailed statements may lag the summary. No EPS growth forecast, target price or intrinsic value.")

def summarize(report,today):
    data,source=_block(report,"income_statement")
    cash,cash_source=_block(report,"cash_flow")
    values={k:_values(data,"detail_rows",k,today) for k in INCOME_NAMES}
    # Separate bridges keep legitimate partial data without imputing missing values.
    revenue=[]
    for period in _recent_common([values[k] for k in ("revenue","other income","total revenue")],today):
        a,b,total=(values[k][period] for k in ("revenue","other income","total revenue"))
        difference=_rounded(a+b-total)
        if difference is None or total<=0:
            continue
        revenue.append({"period":period,"revenue":a,"other_income":b,"total_revenue":total,
                        "other_income_percent":_rounded(100*b/total),"reconciliation_difference":difference})
    pretax=[]
    for period in _recent_common([values[k] for k in ("total revenue","total expenses","profit before tax")],today):
        total,expenses,profit=(values[k][period] for k in ("total revenue","total expenses","profit before tax"))
        difference=_rounded(total-expenses-profit)
        if difference is None or total<=0:
            continue
        pretax.append({"period":period,"total_revenue":total,"total_expenses":expenses,"profit_before_tax":profit,
                       "pretax_margin_percent":_rounded(100*profit/total),"reconciliation_difference":difference})
    taxes=[]
    for period in _recent_common([values[k] for k in ("profit before tax","tax","profit after tax")],today):
        profit,tax,after=(values[k][period] for k in ("profit before tax","tax","profit after tax"))
        difference=_rounded(profit-tax-after)
        if difference is None:
            continue
        taxes.append({"period":period,"profit_before_tax":profit,"tax":tax,"profit_after_tax":after,
                      "reported_tax_to_pretax_percent":_rounded(100*tax/profit) if profit>0 else None,
                      "reconciliation_difference":difference})
    operating=_values(cash,"rows","operating",today)
    cash_quality=[]
    for period in _recent_common([values["profit after tax"],operating],today):
        after=values["profit after tax"][period]
        ocf=operating[period]
        diff=_rounded(ocf-after)
        if diff is None:
            continue
        cash_quality.append({"period":period,"profit_after_tax":after,"operating_cash_flow":ocf,
                             "cash_minus_profit":diff,
                             "cash_to_profit_ratio":_rounded(ocf/after) if after>0 else None})
    # Compare summary and detailed dates explicitly. Never splice older detail
    # into the latest summary or assume the two reported profit bases identical.
    summary_revenue=_values(data,"rows","revenue",today)
    summary_profit=_values(data,"rows","net_profit",today)
    latest_summary=max([*summary_revenue,*summary_profit],default=None)
    latest_detail=max((p for series in values.values() for p in series),default=None)
    scope_status=("DETAIL_OLDER_THAN_SUMMARY" if latest_summary and latest_detail and latest_detail<latest_summary
                  else "LATEST_PERIOD_LABELS_MATCH" if latest_summary and latest_detail==latest_summary
                  else "SUMMARY_DETAIL_COMPARABILITY_UNVERIFIED")
    return {"status":"REPORTED_EARNINGS_BRIDGES" if revenue or pretax or taxes or cash_quality else "INSUFFICIENT_MATCHED_EVIDENCE",
            "unit":"INR_CRORE","revenue_bridge":revenue,"pretax_bridge":pretax,"tax_bridge":taxes,
            "cash_quality":cash_quality,"latest_summary_period":latest_summary,"latest_detail_period":latest_detail,
            "period_scope_status":scope_status,"income_source":source if revenue or pretax or taxes or cash_quality else None,
            "cash_source":cash_source if cash_quality else None,"valuation_eligible":False,"fair_value":None,
            "valuation_blockers":["DATED_PRICE_AND_MULTIPLE_BASIS_REQUIRED","VERIFIED_SHARE_AND_EPS_BASIS_REQUIRED",
                                  "INDEPENDENT_FILING_AND_FORWARD_ESTIMATES_REQUIRED"],"notice":NOTICE}
