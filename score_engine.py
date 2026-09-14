from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Production score: three independent components.
TRADER_WEIGHT = 0.30
TECHNICAL_WEIGHT = 0.35
FUNDAMENTAL_WEIGHT = 0.35
ALERT_THRESHOLD = 80.0
WATCH_THRESHOLD = 65.0

# The raw scanner components are intentionally conservative. For the
# production score we soften that penalty so a good setup can reach the
# upper score range without changing the underlying signals.
TRADER_RELAXATION = 0.45
TECHNICAL_RELAXATION = 0.40


def _num(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _relax_score(value: float | None, relaxation: float) -> float | None:
    if value is None:
        return None
    value = max(0.0, min(100.0, float(value)))
    # Reduce the distance to 100 instead of artificially adding fixed points.
    return value + (100.0 - value) * relaxation


def _weighted(parts: list[tuple[float | None, float]]) -> float | None:
    usable = [(float(value), weight) for value, weight in parts if _num(value) is not None]
    if not usable:
        return None
    weight_sum = sum(weight for _, weight in usable)
    if weight_sum <= 0:
        return None
    return sum(value * weight for value, weight in usable) / weight_sum


def calculate_score(row: pd.Series | dict[str, Any]) -> dict[str, float | str | None]:
    """Calculate the production score from trader, technical and fundamentals.

    Analyst data is intentionally excluded. Trader and technical are
    calibrated less harshly because their raw scanner scores are deliberately
    conservative. Fundamentals remain unchanged.
    """
    raw_trader = _num(row.get("trader_similarity_score"))
    raw_technical = _num(row.get("technical_score"))
    fundamental = _num(row.get("fundamental_score"))

    trader = _relax_score(raw_trader, TRADER_RELAXATION)
    technical = _relax_score(raw_technical, TECHNICAL_RELAXATION)

    overall = _weighted([
        (trader, TRADER_WEIGHT),
        (technical, TECHNICAL_WEIGHT),
        (fundamental, FUNDAMENTAL_WEIGHT),
    ])

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
        "signal": signal,
    }
