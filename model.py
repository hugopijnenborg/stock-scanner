from __future__ import annotations

import numpy as np
import pandas as pd


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(np.clip(x, lo, hi)) if pd.notna(x) else 0.0


def low_is_good(value: float, start: float, extreme: float) -> float:
    """Score a negative metric where more negative is more oversold."""
    if pd.isna(value):
        return 0.0
    return clamp((start - value) / (start - extreme))


def high_is_good(value: float, start: float, extreme: float) -> float:
    if pd.isna(value):
        return 0.0
    return clamp((value - start) / (extreme - start))


def support_component(r: pd.Series) -> float:
    """Reward price being close to a recent low without requiring an exact low."""
    distances = [r.get("distance_support_20d"), r.get("distance_support_60d"), r.get("distance_support_120d")]
    values = [float(x) for x in distances if pd.notna(x)]
    if not values:
        return 0.0
    # 0% above support is strongest. 10%+ above support gets little credit.
    return float(np.mean([clamp((0.10 - x) / 0.10) for x in values]))


def rebound_components(r: pd.Series) -> dict[str, float]:
    return {
        "drawdown_5d": low_is_good(r.get("return_5d", np.nan), -0.05, -0.30),
        "drawdown_20d": low_is_good(r.get("return_20d", np.nan), -0.05, -0.40),
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 45, 20),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.5, -3.0),
        "volume_ratio": high_is_good(r.get("volume_ratio", np.nan), 1.0, 4.0),
        "bollinger_pct": low_is_good(r.get("bollinger_pct", np.nan), 0.35, -0.05),
        "distance_sma20": low_is_good(r.get("distance_sma20", np.nan), -0.03, -0.25),
        "distance_sma50": low_is_good(r.get("distance_sma50", np.nan), -0.03, -0.30),
        "relative_strength_20d": low_is_good(r.get("relative_strength_20d", np.nan), -0.02, -0.25),
        "support": support_component(r),
        "intraday_reversal": high_is_good(r.get("close_location", np.nan), 0.50, 1.00),
        "market_regime": 0.5,
    }


def quality_components(r: pd.Series) -> dict[str, float]:
    return {
        "distance_52w_high": low_is_good(r.get("distance_52w_high", np.nan), -0.05, -0.50),
        "distance_sma200": low_is_good(r.get("distance_sma200", np.nan), -0.02, -0.30),
        "drawdown_20d": low_is_good(r.get("return_20d", np.nan), -0.05, -0.40),
        "relative_strength_20d": low_is_good(r.get("relative_strength_20d", np.nan), -0.10, -0.25),
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 50, 25),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.5, -3.0),
        "volume_ratio": high_is_good(r.get("volume_ratio", np.nan), 1.0, 3.0),
        "support": support_component(r),
        "market_regime": 0.5,
        # Kept explicit until fundamental and Street data are connected.
        "fundamental_placeholder": 0.0,
    }


def cyclical_components(r: pd.Series) -> dict[str, float]:
    return {
        "drawdown_5d": low_is_good(r.get("return_5d", np.nan), -0.05, -0.35),
        "drawdown_20d": low_is_good(r.get("return_20d", np.nan), -0.05, -0.50),
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 45, 20),
        "atr_pct": high_is_good(r.get("atr_pct", np.nan), 0.03, 0.15),
        "volume_ratio": high_is_good(r.get("volume_ratio", np.nan), 1.0, 4.0),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.5, -3.0),
        "relative_strength_20d": low_is_good(r.get("relative_strength_20d", np.nan), -0.05, -0.30),
        "bollinger_pct": low_is_good(r.get("bollinger_pct", np.nan), 0.35, -0.05),
        "support": support_component(r),
        "intraday_reversal": high_is_good(r.get("close_location", np.nan), 0.50, 1.00),
        "market_regime": 0.5,
    }


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    usable = [(k, w) for k, w in weights.items() if k in components and pd.notna(components[k])]
    total = sum(w for _, w in usable)
    if total <= 0:
        return 0.0
    return 100.0 * sum(components[k] * w for k, w in usable) / total


def technical_opportunity_score(r: pd.Series) -> dict[str, float]:
    """Research score matching the trader-chat concept without fake fundamentals.

    85% is technical/market/sector opportunity. Fundamental and Street
    confirmation are deliberately separate until historical data for those
    fields is available.
    """
    c = rebound_components(r)
    # The weights below sum to 0.85. We normalize over available features.
    weights = {
        "drawdown_5d": 0.15,
        "rsi_14": 0.15,
        "distance_sma20": 0.05,
        "distance_sma50": 0.05,
        "drawdown_20d": 0.10,
        "z_score": 0.10,
        "volume_ratio": 0.10,
        "support": 0.10,
        "intraday_reversal": 0.05,
        "relative_strength_20d": 0.05,
        "market_regime": 0.05,
    }
    return {"technical_opportunity_score": weighted_score(c, weights)}


def reversal_trigger(r: pd.Series) -> float:
    """Separate trigger: evidence that selling pressure may be exhausting."""
    signals = []
    if pd.notna(r.get("close_location")):
        signals.append(clamp((r["close_location"] - 0.45) / 0.55))
    if pd.notna(r.get("macd_histogram_change")):
        signals.append(clamp((r["macd_histogram_change"] + abs(r.get("macd_histogram", 0.0))) / (abs(r.get("macd_histogram", 0.0)) + 1e-9)))
    if pd.notna(r.get("return_1d")):
        signals.append(clamp((r["return_1d"] + 0.15) / 0.20))
    return float(np.mean(signals)) if signals else 0.0


def score_row(row: pd.Series, rebound_weights: dict, quality_weights: dict, cyclical_weights: dict) -> dict:
    rb = rebound_components(row)
    qu = quality_components(row)
    cy = cyclical_components(row)
    scores = {
        "rebound_score": weighted_score(rb, rebound_weights),
        "quality_score": weighted_score(qu, quality_weights),
        "cyclical_score": weighted_score(cy, cyclical_weights),
    }
    technical = technical_opportunity_score(row)
    scores.update(technical)
    scores["reversal_trigger"] = reversal_trigger(row) * 100.0
    setup = max(
        ["rebound_score", "quality_score", "cyclical_score"],
        key=lambda k: scores[k],
    ).replace("_score", "")
    scores["setup_type"] = setup
    scores["overall_score"] = scores["technical_opportunity_score"]
    return scores
