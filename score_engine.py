from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Production score: four independent components.
TRADER_WEIGHT = 0.35
TECHNICAL_WEIGHT = 0.30
FUNDAMENTAL_WEIGHT = 0.20
ANALYST_WEIGHT = 0.15
ALERT_THRESHOLD = 80.0
WATCH_THRESHOLD = 65.0


def _num(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _weighted(parts: list[tuple[float | None, float]]) -> float | None:
    usable = [(float(value), weight) for value, weight in parts if _num(value) is not None]
    if not usable:
        return None
    weight_sum = sum(weight for _, weight in usable)
    if weight_sum <= 0:
        return None
    return sum(value * weight for value, weight in usable) / weight_sum


def _calibrate_overall(value: float) -> float:
    """Expand a compressed middle range while keeping 50 as neutral."""
    return float(max(0.0, min(100.0, 50.0 + 1.15 * (value - 50.0))))


def calculate_score(row: pd.Series | dict[str, Any]) -> dict[str, float | str | None]:
    """Calculate the production score from trader, technical, fundamentals and analysts."""
    trader = _num(row.get("trader_similarity_score"))
    technical = _num(row.get("technical_score"))
    fundamental = _num(row.get("fundamental_score"))
    analyst = _num(row.get("analyst_score"))

    weighted = _weighted([
        (trader, TRADER_WEIGHT),
        (technical, TECHNICAL_WEIGHT),
        (fundamental, FUNDAMENTAL_WEIGHT),
        (analyst, ANALYST_WEIGHT),
    ])
    overall = _calibrate_overall(weighted) if weighted is not None else None

    if overall is None:
        signal = "DATA_INCOMPLETE"
    elif overall >= ALERT_THRESHOLD:
        signal = "ALERT"
    elif overall >= WATCH_THRESHOLD:
        signal = "WATCH"
    else:
        signal = "NO_SIGNAL"

    return {
        "overall_score": round(overall, 1) if overall is not None else None,
        "trader_score": round(trader, 1) if trader is not None else None,
        "technical_score": round(technical, 1) if technical is not None else None,
        "fundamental_score": round(fundamental, 1) if fundamental is not None else None,
        "analyst_score": round(analyst, 1) if analyst is not None else None,
        "signal": signal,
    }
