from __future__ import annotations

import math
from typing import Any

import pandas as pd

# Bump whenever the formula, the weights or the thresholds change. Every scan
# records this next to its scores so historical rows stay comparable: a score
# from one version must never be compared with a score from another.
MODEL_VERSION = "3.0"

# Production score: three independent components, weighted exactly as stated.
#
# There is deliberately no per-component calibration here. An earlier version
# relaxed trader and technical with `v + (100 - v) * r` while leaving
# fundamentals untouched. That transform is affine -- it expands to
# `0.55*trader + 45` and `0.60*technical + 40` -- so it quietly compressed two
# of the three components and left fundamentals as the only one at full
# strength. The stated 30/35/35 was in reality 22.8/29.0/48.3, and every score
# carried a fixed +27.5 floor, which lowered the effective alert bar to about
# 70 on the raw scale. Any calibration added here must be applied to all three
# components, or the weights below stop being true.
TRADER_WEIGHT = 0.30
TECHNICAL_WEIGHT = 0.35
FUNDAMENTAL_WEIGHT = 0.35

ALERT_THRESHOLD = 80.0
WATCH_THRESHOLD = 50.0


def _num(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _weighted(parts: list[tuple[float | None, float]]) -> float | None:
    usable = [(value, weight) for value, weight in parts if value is not None]
    if not usable:
        return None
    weight_sum = sum(weight for _, weight in usable)
    if weight_sum <= 0:
        return None
    return sum(value * weight for value, weight in usable) / weight_sum


def signal_for(overall: float | None) -> str:
    if overall is None:
        return "DATA_INCOMPLETE"
    if overall >= ALERT_THRESHOLD:
        return "ALERT"
    if overall >= WATCH_THRESHOLD:
        return "WATCH"
    return "NO_SIGNAL"


def calculate_score(row: pd.Series | dict[str, Any]) -> dict[str, float | str | None]:
    """Calculate the production score from trader, technical and fundamentals.

    Analyst data is intentionally excluded. The three components enter at their
    stated weights, unmodified, so the published score can be read back as
    `0.30*trader + 0.35*technical + 0.35*fundamentals`. When a component is
    missing the remaining weights are renormalised.
    """
    trader = _num(row.get("trader_similarity_score"))
    technical = _num(row.get("technical_score"))
    fundamental = _num(row.get("fundamental_score"))

    overall = _weighted([
        (trader, TRADER_WEIGHT),
        (technical, TECHNICAL_WEIGHT),
        (fundamental, FUNDAMENTAL_WEIGHT),
    ])

    return {
        "overall_score": round(overall, 1) if overall is not None else None,
        "trader_score": round(trader, 1) if trader is not None else None,
        "technical_score": round(technical, 1) if technical is not None else None,
        "fundamental_score": round(fundamental, 1) if fundamental is not None else None,
        "signal": signal_for(overall),
        "model_version": MODEL_VERSION,
    }
