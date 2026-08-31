from __future__ import annotations

import numpy as np
import pandas as pd


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(np.clip(x, lo, hi)) if pd.notna(x) else 0.0


def rebound_components(r: pd.Series) -> dict[str, float]:
    # These are deliberately simple research features. They are not calibrated yet.
    return {
        "drawdown_5d": clamp((-r.get("return_5d", 0.0) - 0.05) / 0.25),
        "drawdown_20d": clamp((-r.get("return_20d", 0.0) - 0.05) / 0.40),
        "rsi_14": clamp((50 - r.get("rsi_14", 50.0)) / 30),
        "z_score": clamp((-r.get("z_score", 0.0) - 1.0) / 2.0),
        "volume_ratio": clamp((r.get("volume_ratio", 1.0) - 1.0) / 3.0),
        "bollinger_pct": clamp((0.35 - r.get("bollinger_pct", 0.5)) / 0.35),
        "distance_sma20": clamp((-r.get("distance_sma20", 0.0) - 0.03) / 0.20),
        "distance_sma50": clamp((-r.get("distance_sma50", 0.0) - 0.03) / 0.30),
        "relative_strength_20d": clamp((r.get("relative_strength_20d", 0.0) + 0.15) / 0.30),
        "market_regime": 0.5,
    }


def quality_components(r: pd.Series) -> dict[str, float]:
    return {
        "drawdown_20d": clamp((-r.get("return_20d", 0.0) - 0.05) / 0.40),
        "distance_52w_high": clamp((-r.get("distance_52w_high", 0.0) - 0.05) / 0.50),
        "distance_sma200": clamp((-r.get("distance_sma200", 0.0) - 0.02) / 0.30),
        "relative_strength_20d": clamp((r.get("relative_strength_20d", 0.0) + 0.10) / 0.25),
        "rsi_14": clamp((50 - r.get("rsi_14", 50.0)) / 30),
        "z_score": clamp((-r.get("z_score", 0.0) - 0.5) / 2.5),
        "volume_ratio": clamp((r.get("volume_ratio", 1.0) - 1.0) / 3.0),
        "market_regime": 0.5,
        "fundamental_placeholder": 0.5,
    }


def cyclical_components(r: pd.Series) -> dict[str, float]:
    return {
        "drawdown_5d": clamp((-r.get("return_5d", 0.0) - 0.05) / 0.30),
        "drawdown_20d": clamp((-r.get("return_20d", 0.0) - 0.05) / 0.50),
        "rsi_14": clamp((50 - r.get("rsi_14", 50.0)) / 30),
        "atr_pct": clamp((r.get("atr_pct", 0.03) - 0.03) / 0.10),
        "volume_ratio": clamp((r.get("volume_ratio", 1.0) - 1.0) / 3.0),
        "z_score": clamp((-r.get("z_score", 0.0) - 1.0) / 2.5),
        "relative_strength_20d": clamp((r.get("relative_strength_20d", 0.0) + 0.20) / 0.40),
        "bollinger_pct": clamp((0.35 - r.get("bollinger_pct", 0.5)) / 0.35),
        "market_regime": 0.5,
    }


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return 100.0 * sum(components.get(k, 0.0) * w for k, w in weights.items()) / total


def score_row(row: pd.Series, rebound_weights: dict, quality_weights: dict, cyclical_weights: dict) -> dict:
    rb = rebound_components(row)
    qu = quality_components(row)
    cy = cyclical_components(row)
    scores = {
        "rebound_score": weighted_score(rb, rebound_weights),
        "quality_score": weighted_score(qu, quality_weights),
        "cyclical_score": weighted_score(cy, cyclical_weights),
    }
    setup = max(scores, key=scores.get).replace("_score", "")
    scores["setup_type"] = setup
    scores["overall_score"] = scores[f"{setup}_score"]
    return scores
