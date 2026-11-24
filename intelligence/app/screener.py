"""Bounded, on-demand daily market screener. No background polling or forecasts."""
from datetime import date, timedelta
from math import isfinite

from .technical import Candle, compute

MIN_HISTORY = 21
MAX_INSTRUMENTS = 20
MAX_CANDLES = 250

def screen(instruments, load_candles, as_of=None, max_age_days=7, universe_limit=MAX_INSTRUMENTS):
    limit = max(1, min(60, universe_limit))
    today = as_of or date.today()
    rows = []
    skipped = {"NO_HISTORY": 0, "STALE": 0, "INVALID": 0, "MIXED_ADJUSTMENT": 0}
    for instrument in instruments[:limit]:
        try:
            payload = load_candles(instrument["id"])
            raw = payload["candles"]
            candles = [Candle(
                str(x["trade_date"]), float(x["open"]), float(x["high"]),
                float(x["low"]), float(x["close"]), int(x["volume"]),
                str(x["adjustment_status"]), int(x.get("revision", 1))
            ) for x in raw]
            if len(candles) < MIN_HISTORY:
                skipped["NO_HISTORY"] += 1
                continue
            if len({x.adjustment_status for x in candles}) != 1:
                skipped["MIXED_ADJUSTMENT"] += 1
                continue
            if any(not all(isfinite(v) for v in (x.open,x.high,x.low,x.close))
                   or x.close <= 0 or x.high < max(x.open,x.close,x.low)
                   or x.low > min(x.open,x.close) or x.volume < 0 for x in candles):
                skipped["INVALID"] += 1
                continue
            if any(candles[i].date >= candles[i+1].date for i in range(len(candles)-1)):
                skipped["INVALID"] += 1
                continue
            age = (today - date.fromisoformat(candles[-1].date)).days
            if age < 0 or age > max_age_days:
                skipped["STALE"] += 1
                continue
            ind = compute(candles)
            close = candles[-1].close
            previous = candles[-2].close
            change = 100 * (close / previous - 1)
            momentum = ind["momentum_20d"][-1]
            volume = ind["relative_volume_20"][-1]
            rsi = ind["rsi_14"][-1]
            rows.append({
                "id": instrument["id"], "symbol": instrument["symbol"],
                "exchange": instrument["exchange"], "as_of": candles[-1].date,
                "close": round(close, 4), "change_1d_percent": round(change, 3),
                "momentum_20d_percent": round(momentum * 100, 3) if momentum is not None else None,
                "relative_volume_20": round(volume, 3) if volume is not None else None,
                "rsi_14": round(rsi, 2) if rsi is not None else None,
                "adjustment_status": candles[-1].adjustment_status,
                "data_age_calendar_days": age,
            })
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            skipped["INVALID"] += 1
    rows.sort(key=lambda x: (-x["change_1d_percent"], x["exchange"], x["symbol"]))
    return {
        "status": "RESEARCH_ONLY",
        "timeframe": "1d",
        "universe_size": min(len(instruments), limit),
        "eligible_count": len(rows),
        "skipped": skipped,
        "top_gainers": rows[:5],
        "top_losers": sorted(rows, key=lambda x: (x["change_1d_percent"], x["exchange"], x["symbol"]))[:5],
        "momentum_leaders": sorted(
            [x for x in rows if x["momentum_20d_percent"] is not None],
            key=lambda x: (-x["momentum_20d_percent"], x["symbol"])
        )[:5],
        "notice": f"Bounded daily sample of up to {limit} registry instruments; not a full-market top-five ranking, live feed, intraday signal or recommendation.",
    }
