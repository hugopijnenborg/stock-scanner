from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LEARNED_MODEL_PATH = Path("learned_model.json")


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(np.clip(x, lo, hi)) if pd.notna(x) else 0.0


def low_is_good(value: float, start: float, extreme: float) -> float:
    if pd.isna(value):
        return 0.0
    return clamp((start - value) / (start - extreme))


def high_is_good(value: float, start: float, extreme: float) -> float:
    if pd.isna(value):
        return 0.0
    return clamp((value - start) / (extreme - start))


def _neutral_centered_low(value: float, start: float, extreme: float) -> float:
    if pd.isna(value):
        return 0.5
    span = abs(float(start) - float(extreme))
    if span == 0:
        return 0.5
    value = float(value)
    if value <= extreme:
        return 1.0
    if value >= start + span:
        return 0.0
    if value < start:
        return 0.5 + 0.5 * (start - value) / span
    return 0.5 - 0.5 * (value - start) / span


def _neutral_centered_high(value: float, start: float, extreme: float) -> float:
    if pd.isna(value):
        return 0.5
    span = abs(float(extreme) - float(start))
    if span == 0:
        return 0.5
    value = float(value)
    if value >= extreme:
        return 1.0
    if value <= start - span:
        return 0.0
    if value > start:
        return 0.5 + 0.5 * (value - start) / span
    return 0.5 - 0.5 * (start - value) / span


def support_component(r: pd.Series) -> float:
    values = [float(x) for x in [r.get("distance_support_20d"), r.get("distance_support_60d"), r.get("distance_support_120d")] if pd.notna(x)]
    if not values:
        return 0.0
    return float(np.mean([clamp((0.10 - x) / 0.10) for x in values]))


def _technical_support_component(r: pd.Series) -> float:
    values = [float(x) for x in [r.get("distance_support_20d"), r.get("distance_support_60d"), r.get("distance_support_120d")] if pd.notna(x)]
    if not values:
        return 0.5
    return float(np.mean([_neutral_centered_low(x, 0.10, 0.0) for x in values]))


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
        "market_regime": float(r.get("market_regime_score", 0.5)) if pd.notna(r.get("market_regime_score", np.nan)) else 0.5,
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
        "market_regime": float(r.get("market_regime_score", 0.5)) if pd.notna(r.get("market_regime_score", np.nan)) else 0.5,
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
        "market_regime": float(r.get("market_regime_score", 0.5)) if pd.notna(r.get("market_regime_score", np.nan)) else 0.5,
    }


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    usable = [(k, w) for k, w in weights.items() if k in components and pd.notna(components[k])]
    total = sum(w for _, w in usable)
    if total <= 0:
        return 0.0
    return 100.0 * sum(components[k] * w for k, w in usable) / total


def technical_opportunity_score(r: pd.Series) -> dict[str, float]:
    """Return a 0..100 technical setup score focused on early dip/rebound setups."""
    c = {
        "drawdown_5d": _neutral_centered_low(r.get("return_5d", np.nan), -0.05, -0.30),
        "rsi_14": _neutral_centered_low(r.get("rsi_14", np.nan), 45, 20),
        "distance_sma20": _neutral_centered_low(r.get("distance_sma20", np.nan), -0.03, -0.25),
        "distance_sma50": _neutral_centered_low(r.get("distance_sma50", np.nan), -0.03, -0.30),
        "drawdown_20d": _neutral_centered_low(r.get("return_20d", np.nan), -0.05, -0.40),
        "z_score": _neutral_centered_low(r.get("z_score", np.nan), -0.5, -3.0),
        "volume_ratio": _neutral_centered_high(r.get("volume_ratio", np.nan), 1.0, 4.0),
        "support": _technical_support_component(r),
        "intraday_reversal": _neutral_centered_high(r.get("close_location", np.nan), 0.50, 1.00),
        "relative_strength_20d": _neutral_centered_low(r.get("relative_strength_20d", np.nan), -0.02, -0.25),
        "sector_relative_strength_20d": _neutral_centered_high(r.get("sector_relative_strength_20d", np.nan), 0.0, 0.20),
        "market_regime": float(r.get("market_regime_score", 0.5)) if pd.notna(r.get("market_regime_score", np.nan)) else 0.5,
    }
    weights = {
        "drawdown_5d": 0.20,
        "rsi_14": 0.20,
        "distance_sma20": 0.10,
        "distance_sma50": 0.10,
        "drawdown_20d": 0.10,
        "z_score": 0.10,
        "volume_ratio": 0.08,
        "support": 0.07,
        "intraday_reversal": 0.03,
        "relative_strength_20d": 0.02,
        "sector_relative_strength_20d": 0.03,
        "market_regime": 0.07,
    }
    return {"technical_opportunity_score": weighted_score(c, weights)}


def dip_score(r: pd.Series) -> float:
    """Measure how close the current setup is to the desired beaten-down/oversold zone."""
    components = {
        "drawdown_5d": low_is_good(r.get("return_5d", np.nan), -0.04, -0.25),
        "drawdown_20d": low_is_good(r.get("return_20d", np.nan), -0.05, -0.35),
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 40, 22),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.5, -2.5),
        "distance_sma20": low_is_good(r.get("distance_sma20", np.nan), -0.02, -0.20),
        "distance_sma50": low_is_good(r.get("distance_sma50", np.nan), -0.02, -0.25),
        "distance_52w_high": low_is_good(r.get("distance_52w_high", np.nan), -0.05, -0.40),
        "volume": high_is_good(r.get("volume_ratio", np.nan), 1.0, 3.0),
        "support": _technical_support_component(r),
    }
    weights = {
        "drawdown_5d": 0.18,
        "drawdown_20d": 0.15,
        "rsi_14": 0.18,
        "z_score": 0.12,
        "distance_sma20": 0.08,
        "distance_sma50": 0.08,
        "distance_52w_high": 0.10,
        "volume": 0.06,
        "support": 0.05,
    }
    return weighted_score(components, weights)


def reversal_trigger(r: pd.Series) -> float:
    signals = []
    if pd.notna(r.get("close_location")):
        signals.append(clamp((r["close_location"] - 0.45) / 0.55))
    if pd.notna(r.get("macd_histogram_change")):
        hist = float(r.get("macd_histogram", 0.0) or 0.0)
        change = float(r.get("macd_histogram_change", 0.0) or 0.0)
        signals.append(clamp((change + abs(hist)) / (abs(hist) + 1e-9)))
    if pd.notna(r.get("return_1d")):
        signals.append(clamp((r["return_1d"] + 0.15) / 0.20))
    return float(np.mean(signals)) if signals else 0.0


def _learned_score(row: pd.Series) -> float | None:
    if not LEARNED_MODEL_PATH.exists():
        return None
    try:
        payload = json.loads(LEARNED_MODEL_PATH.read_text(encoding="utf-8"))
        features = payload["features"]
        x = pd.to_numeric(row.reindex(features), errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
        mean = np.asarray(payload["mean"], dtype=float)
        scale = np.asarray(payload["scale"], dtype=float)
        coef = np.asarray(payload["coef"], dtype=float)
        z = (x - mean) / np.where(scale == 0, 1.0, scale)
        logit = float(np.dot(coef, z) + payload["intercept"])
        probability = 1.0 / (1.0 + np.exp(-np.clip(logit, -30, 30)))
        return float(probability * 100.0)
    except Exception:
        return None


def score_row(row: pd.Series, rebound_weights: dict, quality_weights: dict, cyclical_weights: dict) -> dict:
    rb = rebound_components(row)
    qu = quality_components(row)
    cy = cyclical_components(row)
    scores = {
        "rebound_score": weighted_score(rb, rebound_weights),
        "quality_score": weighted_score(qu, quality_weights),
        "cyclical_score": weighted_score(cy, cyclical_weights),
    }
    scores.update(technical_opportunity_score(row))
    scores["dip_score"] = dip_score(row)
    scores["reversal_trigger"] = reversal_trigger(row) * 100.0
    setup_key = max(["rebound_score", "quality_score", "cyclical_score"], key=lambda k: scores[k])

    learned = _learned_score(row)
    scores["trader_similarity_score"] = learned if learned is not None else scores["technical_opportunity_score"]
    scores["overall_score"] = (
        0.50 * scores["trader_similarity_score"] + 0.50 * scores["technical_opportunity_score"]
        if learned is not None else scores["technical_opportunity_score"]
    )

    # A watch candidate is not an alert. It is a near-threshold setup with
    # meaningful trader-pattern similarity and a genuine beaten-down profile.
    scores["watch_candidate"] = bool(
        scores["overall_score"] >= 70.0
        and scores["trader_similarity_score"] >= 70.0
        and scores["technical_opportunity_score"] >= 65.0
        and scores["dip_score"] >= 60.0
    )
    scores["setup_type"] = "watch" if scores["watch_candidate"] else setup_key.replace("_score", "")
    return scores
