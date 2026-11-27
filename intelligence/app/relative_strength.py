"""Price-index-relative observations with exact dated window identity, not alpha forecasts."""
from hashlib import sha256
from math import isfinite
from .replay_evidence import session_audit, full_manifest
WINDOWS=(20,60,120,252)
NOTICE="Matched stored NSE regular-session dates, provider-validated adjusted stock observations and Nifty 50 price-index closes. Not total return, independent adjustment certification, sector-relative strength or forecast alpha."
def num(v):
    return type(v) in (int,float) and isfinite(v)
def date_digest(dates):
    return sha256("\n".join(dates).encode()).hexdigest()
def benchmark_windows(indexed,calendar,today):
    result={}
    dates=sorted(indexed)
    for n in WINDOWS:
        if len(dates)<n+1:continue
        days=dates[-n-1:]
        labels=[d.isoformat() for d in days]
        audit=session_audit({"first_date":labels[0],"observations":labels},calendar,"NSE",today)
        if audit["status"]!="STORED_SESSIONS_MATCHED":continue
        change=100*(indexed[days[-1]]/indexed[days[0]]-1)
        if num(change) and abs(change)<=1e9:
            result[str(n)]={"return_percent":round(change,6),"first_date":labels[0],"last_date":labels[-1],"dates_digest":date_digest(labels)}
    return result
def stock_windows(raw,today):
    result={}
    for n in WINDOWS:
        if len(raw)<n+1:continue
        manifest=full_manifest(raw[-n-1:],today)
        if manifest is None or len(manifest["observations"])!=n+1:continue
        result[str(n)]=date_digest(list(manifest["observations"]))
    return result
def compare(row,regime,today):
    result={"status":"UNAVAILABLE","benchmark_key":"NSE_INDEX|Nifty 50","windows":{},"notice":NOTICE}
    if row.get("exchange")!="NSE" or row.get("adjustment_status")!="ADJUSTED":return result
    if regime.get("status")!="OBSERVED_BENCHMARK_REGIME" or regime.get("calendar_checked_on")!=today.isoformat() or regime.get("as_of")!=row.get("as_of"):return result
    for n in WINDOWS:
        k=str(n)
        s=(row.get("momentum_windows") or {}).get(k) or {}
        b=(regime.get("relative_strength_windows") or {}).get(k) or {}
        digest=(row.get("adjusted_window_dates") or {}).get(k)
        if not isinstance(digest,str) or len(digest)!=64 or digest!=b.get("dates_digest"):continue
        if s.get("adjustment_status")!="ADJUSTED" or s.get("first_date")!=b.get("first_date") or s.get("last_date")!=row.get("as_of") or b.get("last_date")!=row.get("as_of"):continue
        stock,index=s.get("return_percent"),b.get("return_percent")
        if not num(stock) or not num(index) or not -100<stock<=1e9 or not -100<index<=1e9:continue
        result["windows"][k]={"stock_return_percent":stock,"index_return_percent":index,"difference_pp":round(stock-index,4),"first_date":b["first_date"],"last_date":b["last_date"]}
    if result["windows"]:result["status"]="MATCHED_PRICE_INDEX_OBSERVATIONS"
    return result
