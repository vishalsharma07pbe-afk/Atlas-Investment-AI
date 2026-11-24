"""Distinct deterministic daily research shortlists, not trade recommendations.

Never turn daily history into intraday evidence or a long-term valuation thesis.
These versioned thresholds are research heuristics, not calibrated probabilities.
"""
from math import isfinite
from statistics import median

HORIZONS = ("INTRADAY", "SWING", "SHORT_TERM", "LONG_TERM")
VERSION = "HORIZON-TECHNICAL-1.0"
MIN_HISTORY = {"SWING": 50, "SHORT_TERM": 100, "LONG_TERM": 200}
BLOCKERS = {
    "INTRADAY": ["FRESH_INTRADAY_BARS_REQUIRED", "LIVE_LIQUIDITY_REQUIRED"],
    "SWING": ["LIVE_LIQUIDITY_NOT_VERIFIED", "EVENT_RISK_NOT_VERIFIED", "STRATEGY_BACKTEST_NOT_VERIFIED"],
    "SHORT_TERM": ["FUNDAMENTALS_NOT_VERIFIED", "VALUATION_NOT_VERIFIED", "EVENT_RISK_NOT_VERIFIED"],
    "LONG_TERM": ["FUNDAMENTALS_NOT_VERIFIED", "VALUATION_NOT_VERIFIED", "BUSINESS_QUALITY_NOT_VERIFIED"],
}


def evaluate(candles, indicators, base):
    """Use the screener's already validated OHLCV and computed indicators."""
    result = {}
    close = candles[-1].close
    def latest(key):
        value = indicators[key][-1]
        return value if value is not None and isfinite(value) else None

    rsi = latest("rsi_14")
    atr = latest("atr_14")
    relative = latest("relative_volume_20")
    sma20, sma50, sma100, sma200 = (latest(f"sma_{n}") for n in (20, 50, 100, 200))
    turnover = median(c.close*c.volume for c in candles[-20:])
    atr_pct = 100*atr/close if atr is not None else None
    momentum = latest("momentum_20d")
    for horizon, minimum in MIN_HISTORY.items():
        if len(candles) < minimum:
            result[horizon] = ("INSUFFICIENT_HISTORY", None)
            continue
        if {c.adjustment_status for c in candles} - {"RAW_UNADJUSTED", "ADJUSTED"}:
            result[horizon] = ("UNKNOWN_ADJUSTMENT", None)
            continue
        required = [rsi, atr_pct, relative, sma20, sma50, momentum]
        if horizon != "SWING":
            required.append(sma100)
        if horizon == "LONG_TERM":
            required.append(sma200)
        if any(x is None or not isfinite(x) for x in required):
            result[horizon] = ("INCOMPLETE_INDICATORS", None)
            continue
        # Historical traded-value proxy only; not an executable liquidity check.
        if turnover < 10_000_000 or candles[-1].volume <= 0:
            result[horizon] = ("LOW_HISTORICAL_TURNOVER", None)
            continue
        if horizon == "SWING":
            passed = close > sma20 > sma50 and 50 <= rsi <= 70 and relative >= 1.2 and 0 < atr_pct <= 5 and momentum > 0
            rank = momentum*100 + min(relative, 3)*2 - atr_pct
            reasons = ["Close above rising 20/50-day averages", "Relative volume at least 1.2x", "RSI 50–70 and ATR within 5%"]
            window = "2–20 trading sessions (review horizon)"
        elif horizon == "SHORT_TERM":
            change = close/candles[-61].close-1
            passed = close > sma50 > sma100 and 45 <= rsi <= 72 and 0 < atr_pct <= 4 and change > 0
            rank = change*100 - atr_pct
            reasons = ["Close above 50/100-day averages", "Positive 60-session momentum", "Daily ATR within 4%"]
            window = "1–3 months (review horizon)"
        else:
            change = close/candles[-121].close-1
            passed = close > sma200 and sma50 > sma200 and 0 < atr_pct <= 4 and change > 0
            rank = change*100 - atr_pct
            reasons = ["Close and 50-day average above 200-day average", "Positive 120-session momentum", "Business and valuation evidence still required"]
            window = "6–24 months (research horizon, not a holding instruction)"
        if not passed:
            result[horizon] = ("RULES_NOT_MET", None)
            continue
        warnings = ["Historical liquidity proxy only; current spread and execution liquidity unknown."]
        if candles[-1].adjustment_status == "RAW_UNADJUSTED":
            warnings.append("Raw prices; corporate actions can distort historical signals.")
        result[horizon] = ("TECHNICAL_WATCH", {**base,
            "rank_score": round(rank, 4), "review_horizon": window,
            "history_count": len(candles), "atr_percent": round(atr_pct, 2),
            "median_daily_traded_value": round(turnover, 2),
            "reasons": reasons, "warnings": warnings})
    return result


def summarize(evaluations):
    output = {}
    for horizon in HORIZONS:
        counts = {}
        candidates = []
        if horizon != "INTRADAY":
            for record in evaluations:
                state, candidate = record[horizon]
                counts[state] = counts.get(state, 0)+1
                if candidate is not None:
                    candidates.append(candidate)
        candidates.sort(key=lambda row: (-row["rank_score"], row["exchange"], row["symbol"], row["id"]))
        output[horizon] = {"methodology": VERSION,
            "status": "TECHNICAL_WATCH_ONLY" if candidates else "NO_QUALIFIED_EVIDENCE",
            "candidates": candidates[:5], "matched_count": len(candidates),
            "evaluated_count": len(evaluations) if horizon != "INTRADAY" else 0,
            "exclusions": {k:v for k,v in counts.items() if k!="TECHNICAL_WATCH"},
            "blockers": BLOCKERS[horizon],
            "notice": "Rule-based technical research only. No buy/sell call, target, stop-loss, or probability of profit."}
    return output
