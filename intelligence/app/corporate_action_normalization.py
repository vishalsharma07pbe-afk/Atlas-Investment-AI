"""Price-only normalization of explicitly recorded split/bonus multipliers.

A diagnostic read model, not a certified adjusted series. No storage mutation,
dividend reinvestment, point-in-time replay, or recommendation eligibility.
"""
import json
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import re
from math import isfinite


def preview(candles,instrument):
    blocked={"status":"NORMALIZATION_WITHHELD","reason":"ACTION_CONTEXT_UNVERIFIED"}
    try:
        if not candles or {c.adjustment_status for c in candles}!={"RAW_UNADJUSTED"}:
            return blocked
        isin=instrument.get("isin")
        if not isinstance(isin,str) or not re.fullmatch(r"IN[A-Z0-9]{10}",isin):
            return blocked
        raw=instrument.get("corporate_action_context")
        if not isinstance(raw,str) or len(raw)>40000:
            return blocked
        actions=json.loads(raw)
        if not isinstance(actions,list) or len(actions)>32:
            return {**blocked,"reason":"ACTION_CONTEXT_LIMIT_OR_INVALID"}
        days=[date.fromisoformat(c.date) for c in candles]
        if any(not 0<(b-a).days<=7 for a,b in zip(days,days[1:])):
            return {**blocked,"reason":"HISTORY_GAP_OR_DUPLICATE"}
        first,last=days[0],days[-1]
        relevant={}
        for row in actions:
            day=date.fromisoformat(row["ex_date"])
            if day>last:
                return blocked
            if day<=first:
                continue
            # Multiple revisions/events on one date are deliberately not guessed.
            if day in relevant:
                return {**blocked,"reason":"CONFLICTING_ACTION_RECORDS"}
            if row.get("action_type") not in ("SPLIT","BONUS"):
                return {**blocked,"reason":"UNSUPPORTED_CORPORATE_ACTION"}
            if row.get("isin")!=isin or row.get("ratio_basis")!="POST_SHARES_PER_PRE_SHARE" or not row.get("source_revision"):
                return blocked
            ratio=Decimal(row["ratio"])
            cash=Decimal(row["cash_amount"]) if row.get("cash_amount") is not None else Decimal(0)
            if not ratio.is_finite() or not cash.is_finite() or cash!=0 or not Decimal(".001")<=ratio<=1000 or ratio==1:
                return blocked
            if row["action_type"]=="BONUS" and ratio<=1:
                return blocked
            if day not in days:
                return {**blocked,"reason":"MISSING_EX_DATE_OBSERVATION"}
            relevant[day]=(ratio,row["action_type"])
        if not relevant or max(relevant).isoformat()!=instrument.get("latest_action_date"):
            return blocked
        with localcontext() as ctx:
            ctx.prec=40
            factor=Decimal(1)
            prices=[]
            for day,candle in reversed(list(zip(days,candles))):
                value=Decimal(str(candle.close))
                if not value.is_finite() or value<=0:
                    return blocked
                prices.append(value/factor)
                if day in relevant:
                    factor*=relevant[day][0]
            prices.reverse()
            def change(n):
                value=float((prices[-1]/prices[-n]-1)*100)
                if not isfinite(value):
                    raise ValueError("NONFINITE_RETURN")
                return round(value,4)
            return {"status":"KNOWN_ACTIONS_NORMALIZED_PRICE_ONLY",
                    "first_date":first.isoformat(),"as_of":last.isoformat(),
                    "observations":len(prices),"actions":[{"ex_date":d.isoformat(),"action_type":kind,
                        "post_shares_per_pre_share":str(ratio)} for d,(ratio,kind) in sorted(relevant.items())],
                    "change_1d_percent":change(2) if len(prices)>=2 else None,
                    "change_20_observation_percent":change(21) if len(prices)>=21 else None,
                    "window_price_change_percent":change(len(prices)),
                    "notice":"Known split/bonus records only. Price change, not total return. Completeness, source rights and point-in-time history are not verified. Excluded from rankings and strategy validation."}
    except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation,OverflowError,ZeroDivisionError):
        return blocked
