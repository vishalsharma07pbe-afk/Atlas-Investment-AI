"""Bounded, on-demand daily market screener. No background polling or forecasts."""
from datetime import date, timedelta
from math import isfinite

from .technical import Candle, compute
from .horizon_research import evaluate, summarize, MIN_HISTORY as HORIZON_MIN_HISTORY
from .price_structure import analyze as price_structure
from .corporate_action_normalization import preview as action_preview, reported_crossings, archived_crossings
from .replay_evidence import fingerprint, exact_isin
from . import price_volume_pressure, steady_momentum, relative_strength, company_venues, sector_price_context, score_calibration, fip_research, bracket_research

MIN_HISTORY = 21
MAX_INSTRUMENTS = 20
MAX_CANDLES = 250

def report_close_history(candles):
    """Bounded observed closes from the already validated screener history."""
    return {"adjustment_status": candles[-1].adjustment_status,
            "as_of": candles[-1].date,
            "points": [{"date": c.date, "close": round(c.close, 4)} for c in candles[-30:]]}


def screen(instruments, load_candles, as_of=None, max_age_days=7, universe_limit=MAX_INSTRUMENTS, include_horizons=False, *, batch_loaded=False, expected_session=None, action_reports=None, instant=None, fip_dates=(), action_events=None):
    limit = max(1, min(200 if batch_loaded else 60, universe_limit))
    today = as_of or date.today()
    rows = []
    steady_candidates=[]
    annual_depth_count=0
    horizon_evaluations = []
    breadth_pairs={}
    pressure_rows=[]
    pressure_eligible=0
    trap_eligible=0
    trap_rows=[]
    company_research_universe=[]
    venue_observations={}
    replay_research_universe=[]
    action_previews=[]
    action_preview_count=0
    action_preview_withheld=0
    provider_crossing_count=0
    provider_crossings=[]
    history_coverage = {h:0 for h in HORIZON_MIN_HISTORY}
    skipped = {"NO_HISTORY": 0, "STALE": 0, "INVALID": 0, "MIXED_ADJUSTMENT": 0}
    if batch_loaded:
        skipped["RAW_CORPORATE_ACTION"] = 0
        skipped["ADJUSTED_ACTION_RECONCILIATION"] = 0
        skipped["SESSION_MISMATCH"] = 0
        skipped["REPORTED_SUSPENSION"] = 0
    for instrument in instruments[:limit]:
        if batch_loaded and exact_isin(instrument.get("isin")) and instrument.get("exchange") in ("NSE","BSE") and isinstance(instrument.get("symbol"),str):
            venue_observations[instrument["id"]]=company_venues.observation(instrument)
        if batch_loaded and instrument.get("security_state")=="SUSPENDED_REPORTED":
            skipped["REPORTED_SUSPENSION"]+=1
            continue
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
                first_day=date.fromisoformat(candles[0].date)
                # The cached provider report may reveal a crossing absent from
                # the separate local action ledger. It cannot authorize adjustment.
                isin=instrument.get("isin")
                crossings=reported_crossings((action_reports or {}).get(isin),isin,first_day,last_day,instant) if instant is not None else []
                crossings=archived_crossings([*crossings,*(action_events or {}).get(isin,[])],first_day,last_day)
                raw_history=candles[-1].adjustment_status=="RAW_UNADJUSTED"
                if crossings:
                    provider_crossing_count+=1
                    if len(provider_crossings)<5:
                        provider_crossings.append({"symbol":instrument["symbol"],"exchange":instrument["exchange"],
                            "events":crossings,"status":"REPORTED_ACTION_RECONCILIATION_REQUIRED"})
                if raw_history and (crossings or (event is not None and first_day<date.fromisoformat(event)<=last_day)):
                    skipped["RAW_CORPORATE_ACTION"] += 1
                    # A complete stored calendar suffix can confirm the dates, not event completeness.
                    calendar_dates=fip_dates[-len(candles):] if len(fip_dates)>=len(candles) else ()
                    # A newly reported crossing may not be represented in the
                    # explicitly normalized local ledger. Don't imply the preview
                    # reconciles every event when that is not established.
                    normalized=action_preview(candles,instrument,expected_dates=calendar_dates) if not crossings else {"status":"NORMALIZATION_WITHHELD"}
                    if normalized["status"]=="KNOWN_ACTIONS_NORMALIZED_PRICE_ONLY":
                        action_preview_count+=1
                        if len(action_previews)<5:
                            action_previews.append({"symbol":instrument["symbol"],"exchange":instrument["exchange"],**normalized})
                    else:
                        action_preview_withheld+=1
                    continue
                # An ADJUSTED label is not proof that a recorded/reported event was reconciled.
                # Keep strict FIP, bracket, comparative and replay inputs out of this case.
                if not raw_history and (crossings or (event is not None and first_day<date.fromisoformat(event)<=last_day)):
                    skipped["ADJUSTED_ACTION_RECONCILIATION"] += 1
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
                "security_state":instrument.get("security_state","UNKNOWN"),
            }
            if include_horizons and batch_loaded and expected_session is not None and exact_isin(instrument.get("isin")):
                steady=steady_momentum.technical(candles,ind)
                if steady:
                    swing_structure=price_structure(candles,ind,"SWING",calendar_verified=True)
                    strict_bracket=bracket_research.observe(raw,swing_structure,"SWING",fip_dates,today) if fip_dates else None
                    reported_fip=fip_research.observe_reported(raw,fip_dates,today) if fip_dates and row["adjustment_status"]=="RAW_UNADJUSTED" else None
                    steady_candidates.append({**steady,"reported_fip_evidence":reported_fip,"bracket_research":strict_bracket,"historical_swing_structure":swing_structure,"adjusted_window_dates":relative_strength.stock_windows(raw,today),"security_state":row["security_state"],"report_close_history":report_close_history(candles),"id":row["id"],"symbol":row["symbol"],"exchange":row["exchange"],"isin":instrument["isin"],"as_of":row["as_of"]})
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
            comparative={}
            if batch_loaded and expected_session is not None and exact_isin(instrument.get("isin")) and row["adjustment_status"]=="ADJUSTED" and row["security_state"] not in sector_price_context.SPECIAL:
                comparative=sector_price_context.windows(raw,today)
            if include_horizons:
                evidence_hash=fingerprint(raw,today) if batch_loaded else None
                evaluation=evaluate(candles, ind, row)
                for state,candidate in evaluation.values():
                    if candidate is not None:
                        if batch_loaded and exact_isin(instrument.get("isin")):
                            candidate["isin"]=instrument["isin"]
                        if evidence_hash is not None:
                            candidate["replay_evidence_hash"]=evidence_hash
                paths=steady_momentum.window_observations(candles) if comparative and any(c is not None for _,c in evaluation.values()) else {}
                for horizon, (state,candidate) in evaluation.items():
                    if candidate is not None:
                        candidate["price_structure"]=price_structure(candles,ind,horizon,
                            calendar_verified=batch_loaded and expected_session is not None)
                        if batch_loaded:
                            if fip_dates:
                                bracket=bracket_research.observe(raw,candidate["price_structure"],horizon,fip_dates,today)
                                if bracket is not None:candidate["bracket_research"]=bracket
                            candidate["security_state"]=row["security_state"]
                            candidate["report_close_history"]=report_close_history(candles)
                            n=score_calibration.WINDOW.get(horizon)
                            if n and str(n) in comparative:
                                candidate["score_window"]=comparative[str(n)]
                                candidate["score_risk_path"]=paths.get(str(n))
                horizon_evaluations.append(evaluation)
                for horizon,minimum in HORIZON_MIN_HISTORY.items():
                    if len(candles)>=minimum:
                        history_coverage[horizon]+=1
            if batch_loaded and expected_session is not None and candles[-1].adjustment_status=="ADJUSTED":
                key=candles[-2].date
                counts=breadth_pairs.setdefault(key,{"advancing":0,"declining":0,"unchanged":0})
                counts["advancing" if close>previous else "declining" if close<previous else "unchanged"]+=1
            if batch_loaded and exact_isin(instrument.get("isin")):
                row["isin"]=instrument["isin"]
            rows.append(row)
            # Observation depth only, not verified continuity or adjusted evidence.
            if batch_loaded and expected_session is not None and len(candles)>=253:
                annual_depth_count+=1
            if batch_loaded and exact_isin(instrument.get("isin")):
                identity={"id":row["id"],"exchange":row["exchange"],"isin":instrument["isin"],"as_of":row["as_of"],"first_date":candles[0].date}
                # Collect comparable returns for the broad valid sample, not
                # only bullish candidates. Reuse the already loaded histories.
                if expected_session is not None:
                    identity["security_state"]=row["security_state"]
                    if row["adjustment_status"]=="ADJUSTED" and row["security_state"] not in sector_price_context.SPECIAL:
                        identity["comparative_price_windows"]=comparative
                        if fip_dates and fip_dates[-1]==row["as_of"]:
                            fip=fip_research.observe(raw,fip_dates,today)
                            if fip is not None:
                                # Only matching rows need the full metrics in
                                # the broad snapshot; keep status/reasons for
                                # coverage and strict Elite review of others.
                                identity["fip_research"]=fip if fip["status"]=="FIP_PRICE_MATCH" else {k:v for k,v in fip.items() if k!="windows"}
                if expected_session is not None and row["security_state"] not in sector_price_context.SPECIAL:
                    from . import multi_strategy
                    features=multi_strategy.price_features(candles,fip_dates)
                    if features is not None:
                        identity["symbol"]=row["symbol"]
                        identity["multi_strategy_price"]=features
                company_research_universe.append(identity)
                if instrument["id"] in venue_observations:
                    venue_observations[instrument["id"]]=company_venues.observation(instrument,candles)
                # A recent validated adjusted window is a scheduling hint only.
                # The replay worker still validates its complete 500-row input.
                if len(candles)>=250 and 1<=age<=4 and fingerprint(raw,today) is not None:
                    replay_research_universe.append(identity)
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            skipped["INVALID"] += 1
    rows.sort(key=lambda x: (-x["change_1d_percent"], x["exchange"], x["symbol"],x["id"]))
    result = {
        "status": "RESEARCH_ONLY",
        "timeframe": "1d",
        "universe_size": min(len(instruments), limit),
        "eligible_count": len(rows),
        "skipped": skipped,
        "top_gainers": rows[:5],
        "top_losers": sorted(rows, key=lambda x: (x["change_1d_percent"], x["exchange"], x["symbol"],x["id"]))[:5],
        "momentum_leaders": sorted(
            [x for x in rows if x["momentum_20d_percent"] is not None],
            key=lambda x: (-x["momentum_20d_percent"], x["symbol"],x["id"])
        )[:5],
        "notice": f"Bounded daily sample of up to {limit} registry instruments; not a full-market top-five ranking, live feed, intraday signal or recommendation.",
    }
    if batch_loaded:
        result["annual_depth_count"]=annual_depth_count
        result["steady_momentum_candidates"]=steady_candidates
        result["company_research_universe"]=company_research_universe
        result["venue_observations"]=list(venue_observations.values())
        result["replay_research_universe"]=replay_research_universe
        result["sample_breadth"]={"as_of":expected_session.isoformat() if expected_session is not None else None,
            "adjustment_status":"ADJUSTED","pairs":[{"previous_session":k,**v} for k,v in sorted(breadth_pairs.items())],
            "notice":"Counts of adjusted histories in the selected registry sample, grouped by preceding observed date; not full-exchange breadth."}
        result["corporate_action_review"]={"normalized_preview_count":action_preview_count,
            "withheld_count":action_preview_withheld,"previews":action_previews,
            "provider_crossing_count":provider_crossing_count,"provider_crossings":provider_crossings,
            "notice":"Known-action OHLCV reconstruction is diagnostic only. Unreconciled raw or adjusted crossing histories remain excluded from rankings and backtesting."}
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
