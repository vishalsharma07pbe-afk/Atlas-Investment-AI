"""Price-only normalization of explicitly recorded split/bonus multipliers.

A diagnostic read model, not a certified adjusted series. No storage mutation,
dividend reinvestment, point-in-time replay, or recommendation eligibility.
"""
import json
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
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


# Provider-reported corporate actions are a separate source of review evidence,
# never proof that a historical candle is adjusted or that the ledger is complete.
_ACTION_TYPES={"dividend":"DIVIDEND","bonus":"BONUS","split":"SPLIT","rights":"RIGHTS"}

def _reported_day(value):
    if not isinstance(value,str) or len(value)>20:
        return None
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",value):
            return date.fromisoformat(value).isoformat()
        match=re.fullmatch(r"([0-9]{1,2}) ([A-Za-z]{3}) ([0-9]{4})",value)
        if match:
            months="jan feb mar apr may jun jul aug sep oct nov dec".split()
            return date(int(match[3]),months.index(match[2].lower())+1,int(match[1])).isoformat()
    except ValueError:
        pass
    return None


def normalize_reported_actions(raw):
    rows=[]
    for row in raw[:100]:
        if not isinstance(row,dict) or not isinstance(row.get("name"),str):
            continue
        name=row["name"].strip()[:180]
        day=_reported_day(row.get("expiry_date"))
        if not name or not day:
            continue
        kind=_ACTION_TYPES.get(name.casefold(),"OTHER")
        ratio=row.get("ratio")
        ratio=ratio if isinstance(ratio,str) and re.fullmatch(r"[0-9]{1,9}:[0-9]{1,9}",ratio) else None
        amount=row.get("amount")
        amount=amount if type(amount) in (int,float) and isfinite(amount) and 0<=amount<=1_000_000 else None
        details=[]
        for detail in row.get("event_details",[])[:20] if isinstance(row.get("event_details"),list) else []:
            if isinstance(detail,dict) and isinstance(detail.get("name"),str) and isinstance(detail.get("value"),str):
                details.append({"name":detail["name"][:180],"value":detail["value"][:300]})
        rows.append({"name":name,"date":day,"expiry_date":day,"action_type":kind,
                     "amount":amount,"reported_ratio":ratio,"ratio_basis":"UNVERIFIED",
                     "event_details":details,"adjustment_eligible":False})
    return rows


def reported_crossings(report,isin,first,last,instant):
    """Only positive reported crossing evidence; absence is not completeness."""
    if not isinstance(report,dict) or report.get("isin")!=isin or not isinstance(isin,str) or not re.fullmatch(r"INE[A-Z0-9]{9}",isin):
        return []
    try:
        block=report["sections"]["corporate_actions"]
        source=block["source"]
        stamp=datetime.fromisoformat(source["retrieved_at"])
        if (block["status"]!="AVAILABLE" or source["provider"]!="UPSTOX"
            or stamp.tzinfo is None or not instant-timedelta(hours=24)<=stamp<=instant
            or source.get("endpoint")!="/v2/fundamentals/"+isin+"/corporate-actions"):
            return []
        data=block["data"]
        if not isinstance(data,list) or len(data)>100:
            return []
        found=set()
        for event in data:
            if not isinstance(event,dict) or event.get("adjustment_eligible") is not False:
                continue
            day=_reported_day(event.get("date"))
            kind=event.get("action_type")
            if day and first<date.fromisoformat(day)<=last and kind in (*_ACTION_TYPES.values(),"OTHER"):
                found.add((day,kind))
        return [{"date":d,"action_type":k} for d,k in sorted(found)]
    except (ValueError,TypeError,KeyError,AttributeError):
        return []
