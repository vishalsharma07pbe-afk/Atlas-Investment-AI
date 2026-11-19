"""Leakage-resistant walk-forward evaluation for daily research signals.

Signals are fitted only on earlier observations and evaluated on the next session.
This is model monitoring, not a price forecast or an execution system.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from statistics import mean


@dataclass(frozen=True)
class Point:
    trade_date: date
    close: float


def _points(payload: dict) -> list[Point]:
    raw = payload.get("candles") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raise ValueError("CANDLES_REQUIRED")
    points: list[Point] = []
    statuses: set[str] = set()
    for row in raw:
        current = Point(date.fromisoformat(str(row["trade_date"])), float(row["close"]))
        if not isfinite(current.close) or current.close <= 0:
            raise ValueError("INVALID_CLOSE")
        if points and current.trade_date <= points[-1].trade_date:
            raise ValueError("DATES_NOT_STRICTLY_INCREASING")
        statuses.add(str(row.get("adjustment_status", "UNKNOWN")))
        points.append(current)
    if len(statuses) > 1:
        raise ValueError("MIXED_ADJUSTMENT_STATUS")
    return points


def _feature(closes: list[float], index: int, lookback: int) -> float:
    return closes[index] / closes[index - lookback] - 1


def walk_forward(payload: dict, lookback: int = 20, train_size: int = 120,
                 test_size: int = 20, fee_bps: int = 10) -> dict:
    if not 5 <= lookback <= 100 or not 60 <= train_size <= 1000:
        raise ValueError("INVALID_WINDOW")
    if not 5 <= test_size <= 250 or not 0 <= fee_bps <= 100:
        raise ValueError("INVALID_WINDOW")
    points = _points(payload)
    required = lookback + train_size + test_size + 1
    if len(points) < required:
        return {"status": "INSUFFICIENT_HISTORY", "required_candles": required,
                "observed_candles": len(points), "folds": []}

    closes = [point.close for point in points]
    predictions: list[dict] = []
    folds: list[dict] = []
    fold_start = lookback + train_size
    while fold_start < len(points) - 1:
        test_end = min(fold_start + test_size, len(points) - 1)
        train_start = fold_start - train_size
        train_features = [_feature(closes, i, lookback) for i in range(train_start, fold_start)]
        # The threshold is estimated exclusively from the preceding training window.
        threshold = mean(train_features)
        fold_predictions = []
        for i in range(fold_start, test_end):
            feature = _feature(closes, i, lookback)
            probability = max(0.05, min(0.95, 0.5 + (feature - threshold) * 2.5))
            actual_return = closes[i + 1] / closes[i] - 1
            predicted_up = probability >= 0.5
            actual_up = actual_return > 0
            row = {
                "signal_date": points[i].trade_date.isoformat(),
                "outcome_date": points[i + 1].trade_date.isoformat(),
                "probability_up": round(probability, 6),
                "predicted_direction": "UP" if predicted_up else "DOWN",
                "actual_direction": "UP" if actual_up else "DOWN",
                "actual_return_percent": round(actual_return * 100, 6),
                "correct": predicted_up == actual_up,
            }
            fold_predictions.append(row)
            predictions.append(row)
        folds.append({
            "train_from": points[train_start].trade_date.isoformat(),
            "train_to": points[fold_start - 1].trade_date.isoformat(),
            "test_from": points[fold_start].trade_date.isoformat(),
            "test_to": points[test_end].trade_date.isoformat(),
            "fitted_threshold": round(threshold, 8),
            "observations": len(fold_predictions),
        })
        fold_start = test_end

    brier = mean((row["probability_up"] - (1 if row["actual_direction"] == "UP" else 0)) ** 2
                 for row in predictions)
    accuracy = mean(1 if row["correct"] else 0 for row in predictions)
    cost = fee_bps / 10000
    strategy = 1.0
    benchmark = 1.0
    turnover = 0
    previous_position = 0
    for row in predictions:
        position = 1 if row["predicted_direction"] == "UP" else 0
        if position != previous_position:
            strategy *= 1 - cost
            turnover += 1
        strategy *= 1 + (row["actual_return_percent"] / 100 if position else 0)
        benchmark *= 1 + row["actual_return_percent"] / 100
        previous_position = position

    reliability = []
    for low in (0.0, 0.4, 0.6, 0.8):
        high = {0.0: 0.4, 0.4: 0.6, 0.6: 0.8, 0.8: 1.01}[low]
        bucket = [row for row in predictions if low <= row["probability_up"] < high]
        if bucket:
            reliability.append({"range": f"{low:.1f}-{min(high, 1):.1f}",
                                "count": len(bucket),
                                "mean_probability": round(mean(row["probability_up"] for row in bucket), 4),
                                "observed_up_rate": round(mean(1 if row["actual_direction"] == "UP" else 0 for row in bucket), 4)})

    return {
        "status": "WALK_FORWARD_RESEARCH_ONLY",
        "method": "ROLLING_MOMENTUM_THRESHOLD_NEXT_SESSION_OUTCOME",
        "parameters": {"lookback": lookback, "train_size": train_size,
                       "test_size": test_size, "fee_bps": fee_bps},
        "leakage_controls": ["TRAIN_WINDOW_PRECEDES_TEST_WINDOW", "NEXT_SESSION_OUTCOME",
                             "NO_RANDOM_SHUFFLE", "THRESHOLD_REFIT_PER_FOLD"],
        "observations": len(predictions), "folds": folds,
        "directional_accuracy_percent": round(accuracy * 100, 3),
        "brier_score": round(brier, 6),
        "strategy_return_percent": round((strategy - 1) * 100, 3),
        "benchmark_return_percent": round((benchmark - 1) * 100, 3),
        "turnover_events": turnover, "calibration": reliability,
        "recent_predictions": predictions[-20:],
        "monitoring": {"sample_warning": len(predictions) < 100,
                       "calibration_warning": brier > 0.25,
                       "last_outcome_date": predictions[-1]["outcome_date"]},
        "notice": "Historical out-of-sample evaluation only. Accuracy and returns can degrade; no future price, target, or trade is produced.",
    }
