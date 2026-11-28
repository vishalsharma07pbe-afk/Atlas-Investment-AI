"""Known-action OHLCV reconstruction, strictly separate from provider-adjusted data.

Neither a complete corporate-action ledger nor raw provider semantics is inferred.
No stored candle is changed. Results are excluded from investment qualification.
"""
import hashlib
import json
from datetime import date,datetime,timedelta
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import re
from math import isfinite

VERSION="KNOWN-ACTION-OHLCV-1"
NOTICE=("Known split/bonus records only. Prices and share-equivalent volume are diagnostic; "
        "no dividend reinvestment. Completeness, source rights, raw-price semantics and point-in-time "
        "history are not verified. Excluded from rankings and strategy validation.")

def _hash(value):
    return hashlib.sha256(json.dumps(value,separators=(",",":"),sort_keys=True,allow_nan=False).encode()).hexdigest()

def _fraction(value):
    # Bounded exact decimal inputs; never silently round fractional share volumes.
    if isinstance(value,bool) or len(str(value))>80:
        raise ValueError("INVALID_NUMBER")
    d=Decimal(str(value))
    if not d.is_finite() or abs(d.adjusted())>30:
        raise ValueError("INVALID_NUMBER")
    return Fraction(d)

def _ratio(v):
    return str(v.numerator)+"/"+str(v.denominator)

def _decimal(v):
    with localcontext() as ctx:
        ctx.prec=40
        return str(Decimal(v.numerator)/Decimal(v.denominator))

def reconstruct(candles,instrument,*,expected_dates=()):
    """Pure, bounded reconstruction in last-observation share units.

    OHLC is divided and volume multiplied by the cumulative post/pre share
    multiplier for sessions strictly before each event. Ex-date itself is not
    changed by that event. Exact rational factors/values are fingerprinted;
    decimal projections are display-only. Missing/unsupported action coverage
    is never certified, even if all supplied calendar dates match.
    """
    blocked={"status":"NORMALIZATION_WITHHELD","reason":"ACTION_CONTEXT_UNVERIFIED"}
    try:
        if not 2<=len(candles)<=500 or {c.adjustment_status for c in candles}!={"RAW_UNADJUSTED"}:
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
        dates=tuple(d.isoformat() for d in days)
        if expected_dates and tuple(expected_dates)!=dates:
            return {**blocked,"reason":"STORED_SESSION_MISMATCH"}
        relevant={}
        for row in actions:
            day=date.fromisoformat(row["ex_date"])
            if day>last:
                return blocked
            if day<=first:
                continue
            if day in relevant:
                return {**blocked,"reason":"CONFLICTING_ACTION_RECORDS"}
            kind=row.get("action_type")
            if kind not in ("SPLIT","BONUS"):
                return {**blocked,"reason":"UNSUPPORTED_CORPORATE_ACTION"}
            revision=row.get("source_revision")
            if (row.get("isin")!=isin or row.get("ratio_basis")!="POST_SHARES_PER_PRE_SHARE"
                    or not isinstance(revision,str) or not revision.strip() or len(revision)>120):
                return blocked
            ratio=_fraction(row["ratio"])
            cash=_fraction(row["cash_amount"]) if row.get("cash_amount") is not None else Fraction(0)
            if cash!=0 or not Fraction(1,1000)<=ratio<=1000 or ratio==1 or (kind=="BONUS" and ratio<=1):
                return blocked
            if day not in days:
                return {**blocked,"reason":"MISSING_EX_DATE_OBSERVATION"}
            relevant[day]=(ratio,kind,revision)
        if not relevant or max(relevant).isoformat()!=instrument.get("latest_action_date"):
            return blocked
        # Reject malformed OHLCV rather than fabricate normalized values.
        original=[]
        for day,c in zip(days,candles):
            o,h,l,close,v=(_fraction(x) for x in (c.open,c.high,c.low,c.close,c.volume))
            if min(o,h,l,close)<=0 or h<max(o,l,close) or l>min(o,h,close) or v<0 or v.denominator!=1:
                return {**blocked,"reason":"INVALID_RAW_OHLCV"}
            if type(c.revision) is not int or c.revision<1:
                return {**blocked,"reason":"INVALID_RAW_REVISION"}
            original.append((day,(o,h,l,close,v),c.revision))
        factor=Fraction(1)
        derived=[]
        for day,(o,h,l,close,v),revision in reversed(original):
            values=(o/factor,h/factor,l/factor,close/factor,v*factor)
            derived.append((day,values,factor))
            if day in relevant:
                factor*=relevant[day][0]
        derived.reverse()
        events=[{"ex_date":d.isoformat(),"action_type":kind,"post_shares_per_pre_share":_decimal(ratio),
                 "multiplier_exact":_ratio(ratio),"source_revision":revision}
                for d,(ratio,kind,revision) in sorted(relevant.items())]
        identity=[instrument.get("id"),instrument.get("exchange"),isin]
        raw_digest=_hash([VERSION,identity,[[d.isoformat(),*map(_ratio,values),rev] for d,values,rev in original]])
        actions_digest=_hash([VERSION,identity,events])
        derived_digest=_hash([VERSION,raw_digest,actions_digest,[[d.isoformat(),*map(_ratio,v),_ratio(f)] for d,v,f in derived]])
        rows=[{"trade_date":d.isoformat(),**dict(zip(("open","high","low","close","volume_share_equivalent"),map(_decimal,v))),
               "share_multiplier_exact":_ratio(f),"volume_share_equivalent_exact":_ratio(v[-1])}
              for d,v,f in derived]
        return {"status":"KNOWN_ACTIONS_RECONSTRUCTED_OHLCV","methodology":VERSION,"first_date":first.isoformat(),
                "as_of":last.isoformat(),"observations":len(rows),"actions":events,
                "calendar_status":"STORED_SESSION_DATES_MATCHED" if expected_dates else "SESSION_CONTINUITY_UNVERIFIED",
                "raw_fingerprint":raw_digest,"action_fingerprint":actions_digest,"derived_fingerprint":derived_digest,
                "adjustment_eligible":False,"qualification_eligible":False,"rows":rows,"notice":NOTICE}
    except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation,OverflowError,ZeroDivisionError):
        return blocked

def preview(candles,instrument,*,expected_dates=()):
    """Keep the existing price preview contract; expose only bounded diagnostics."""
    result=reconstruct(candles,instrument,expected_dates=expected_dates)
    if result["status"]=="NORMALIZATION_WITHHELD":
        return result
    try:
        rows=result.pop("rows")
        closes=[Decimal(r["close"]) for r in rows]
        def change(n):
            value=float((closes[-1]/closes[-n]-1)*100)
            if not isfinite(value):
                raise ValueError("NONFINITE_RETURN")
            return round(value,4)
        return {**result,"status":"KNOWN_ACTIONS_NORMALIZED_PRICE_ONLY",
                "change_1d_percent":change(2),
                "change_20_observation_percent":change(21) if len(closes)>=21 else None,
                "window_price_change_percent":change(len(closes)),
                "volume_treatment":"SHARE_EQUIVALENT_NOT_EXECUTED_VOLUME",
                "fractional_share_equivalent_dates":sum(Fraction(r["volume_share_equivalent_exact"]).denominator!=1 for r in rows)}
    except (ValueError,TypeError,InvalidOperation,OverflowError,ZeroDivisionError):
        return {"status":"NORMALIZATION_WITHHELD","reason":"INVALID_DERIVED_VALUES"}


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
