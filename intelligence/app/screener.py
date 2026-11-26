"""Bounded, on-demand daily market screener. No background polling or forecasts."""
from datetime import date, timedelta
from math import isfinite

from .technical import Candle, compute
from .horizon_research import evaluate, summarize, MIN_HISTORY as HORIZON_MIN_HISTORY
from .price_structure import analyze as price_structure
from .corporate_action_normalization import preview as action_preview
from .replay_evidence import fingerprint, exact_isin
from . import price_volume_pressure

MIN_HISTORY = 21
MAX_INSTRUMENTS = 20
MAX_CANDLES = 250

def report_close_history(candles):
    """Bounded observed closes from the already validated screener history."""
    return {"adjustment_status": candles[-1].adjustment_status,
            "as_of": candles[-1].date,
            "points": [{"date": c.date, "close": round(c.close, 4)} for c in candles[-30:]]}


def screen(instruments, load_candles, as_of=None, max_age_days=7, universe_limit=MAX_INSTRUMENTS, include_horizons=False, *, batch_loaded=False, expected_session=None):
    limit = max(1, min(200 if batch_loaded else 60, universe_limit))
    today = as_of or date.today()
    rows = []
    horizon_evaluations = []
    breadth_pairs={}
    pressure_rows=[]
    pressure_eligible=0
    trap_eligible=0
    trap_rows=[]
    action_previews=[]
    action_preview_count=0
    action_preview_withheld=0
    history_coverage = {h:0 for h in HORIZON_MIN_HISTORY}
    skipped = {"NO_HISTORY": 0, "STALE": 0, "INVALID": 0, "MIXED_ADJUSTMENT": 0}
    if batch_loaded:
        skipped["RAW_CORPORATE_ACTION"] = 0
        skipped["SESSION_MISMATCH"] = 0
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
            if any(x.adjustment_status not in ("ADJUSTED","RAW_UNADJUSTED") for x in candles):
                skipped["INVALID"] += 1
                continue
            if len({x.adjustment_status for x in candles}) != 1:
                skipped["MIXED_ADJUSTMENT"] += 1
                continue
            if any(not all(isfinite(v) for v in (x.open,x.high,x.low,x.close))
                   or min(x.open,x.high,x.low,x.close) <= 0 or x.high < max(x.open,x.close,x.low)
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
            if batch_loaded:
                last_day=date.fromisoformat(candles[-1].date)
                if expected_session is not None and last_day!=expected_session:
                    skipped["SESSION_MISMATCH"] += 1
                    continue
                event=instrument.get("latest_action_date")
                if (event is not None and candles[-1].adjustment_status=="RAW_UNADJUSTED"
                    and date.fromisoformat(candles[0].date)<date.fromisoformat(event)<=last_day):
                    skipped["RAW_CORPORATE_ACTION"] += 1
                    normalized=action_preview(candles,instrument)
                    if normalized["status"]=="KNOWN_ACTIONS_NORMALIZED_PRICE_ONLY":
                        action_preview_count+=1
                        if len(action_previews)<5:
                            action_previews.append({"symbol":instrument["symbol"],"exchange":instrument["exchange"],**normalized})
                    else:
                        action_preview_withheld+=1
                    continue
            ind = compute(candles)
            close = candles[-1].close
            previous = candles[-2].close
            change = 100 * (close / previous - 1)
            momentum = ind["momentum_20d"][-1]
            volume = ind["relative_volume_20"][-1]
            rsi = ind["rsi_14"][-1]
            row = {
                "id": instrument["id"], "symbol": instrument["symbol"],
                "exchange": instrument["exchange"], "as_of": candles[-1].date,
                "close": round(close, 4), "change_1d_percent": round(change, 3),
                "momentum_20d_percent": round(momentum * 100, 3) if momentum is not None else None,
                "relative_volume_20": round(volume, 3) if volume is not None else None,
                "rsi_14": round(rsi, 2) if rsi is not None else None,
                "adjustment_status": candles[-1].adjustment_status,
                "data_age_calendar_days": age,
            }
            if include_horizons and batch_loaded:
                pressure=price_volume_pressure.analyze(candles, calendar_verified=expected_session is not None)
                row["price_volume_pressure"]=pressure
                follow=pressure.get("breakout_followthrough") or {}
                if follow.get("status")=="OBSERVED_FOLLOWTHROUGH":
                    trap_eligible+=1
                    if follow.get("events"):
                        trap_rows.append({"id":row["id"],"symbol":row["symbol"],"exchange":row["exchange"],
                            "isin":instrument.get("isin") if exact_isin(instrument.get("isin")) else None,
                            "as_of":row["as_of"],"followthrough":follow})
                if pressure["status"]=="OBSERVED_PRICE_VOLUME_ONLY":
                    pressure_eligible+=1
                    if pressure["findings"]:
                        pressure_rows.append({"id":row["id"],"symbol":row["symbol"],"exchange":row["exchange"],
                            "isin":instrument.get("isin") if exact_isin(instrument.get("isin")) else None,
                            "as_of":row["as_of"],"price_volume_pressure":pressure})
            if include_horizons:
                evidence_hash=fingerprint(raw,today) if batch_loaded else None
                evaluation=evaluate(candles, ind, row)
                for state,candidate in evaluation.values():
                    if candidate is not None and evidence_hash is not None:
                        candidate["replay_evidence_hash"]=evidence_hash
                for horizon, (state,candidate) in evaluation.items():
                    if candidate is not None:
                        candidate["price_structure"]=price_structure(candles,ind,horizon,
                            calendar_verified=batch_loaded and expected_session is not None)
                        if batch_loaded:
                            candidate["report_close_history"]=report_close_history(candles)
                horizon_evaluations.append(evaluation)
                for horizon,minimum in HORIZON_MIN_HISTORY.items():
                    if len(candles)>=minimum:
                        history_coverage[horizon]+=1
            if batch_loaded and expected_session is not None and candles[-1].adjustment_status=="ADJUSTED":
                key=candles[-2].date
                counts=breadth_pairs.setdefault(key,{"advancing":0,"declining":0,"unchanged":0})
                counts["advancing" if close>previous else "declining" if close<previous else "unchanged"]+=1
            rows.append(row)
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            skipped["INVALID"] += 1
    rows.sort(key=lambda x: (-x["change_1d_percent"], x["exchange"], x["symbol"]))
    result = {
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
    if batch_loaded:
        result["sample_breadth"]={"as_of":expected_session.isoformat() if expected_session is not None else None,
            "adjustment_status":"ADJUSTED","pairs":[{"previous_session":k,**v} for k,v in sorted(breadth_pairs.items())],
            "notice":"Counts of adjusted histories in the selected registry sample, grouped by preceding observed date; not full-exchange breadth."}
        result["corporate_action_review"]={"normalized_preview_count":action_preview_count,
            "withheld_count":action_preview_withheld,"previews":action_previews,
            "notice":"Recorded split/bonus normalization diagnostics only. These histories remain excluded from rankings and backtesting."}
    if include_horizons:
        result["horizons"] = summarize(horizon_evaluations)
        if batch_loaded:
            result["breakout_review"]={"evaluated_count":trap_eligible,"event_listing_count":len(trap_rows),
                "items":sorted(trap_rows,key=lambda r:(not any(e["status"]=="REENTRY_OBSERVED" for e in r["followthrough"]["events"]),
                    -max(abs(e["break_percent"]) for e in r["followthrough"]["events"]),r["symbol"],r["id"]))[:5],
                "notice":price_volume_pressure.breakout_followthrough.NOTICE}
            result["price_volume_review"]={"evaluated_count":pressure_eligible,
                "flagged_count":len(pressure_rows),
                "downside_items":sorted([r for r in pressure_rows if any(f in price_volume_pressure.DOWNSIDE for f in r["price_volume_pressure"]["findings"])],
                    key=lambda r:(-r["price_volume_pressure"]["relative_volume"],r["symbol"],r["id"]))[:5],
                "upside_items":sorted([r for r in pressure_rows if any(f in price_volume_pressure.UPSIDE for f in r["price_volume_pressure"]["findings"])],
                    key=lambda r:(-r["price_volume_pressure"]["relative_volume"],r["symbol"],r["id"]))[:5],
                "notice":price_volume_pressure.NOTICE}
        result["history_coverage"] = {h:{"minimum_observations":minimum,"eligible_histories":history_coverage[h]}
                                      for h,minimum in HORIZON_MIN_HISTORY.items()}
    return result
