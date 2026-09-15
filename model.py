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


# A setup still in free fall is discounted, one being absorbed gets a modest
# lift. Bounded on both sides so confirmation can never manufacture an
# opportunity that the drawdown itself does not support.
CONFIRMATION_FLOOR = 0.70
CONFIRMATION_CEILING = 1.15


def _drawdown_component(r: pd.Series) -> float:
    """How hard the stock has fallen over 7, 14 and 30 days.

    This is the opportunity itself: the sharper and more recent the fall, the
    more there is to recover. The three windows answer different questions --
    7d catches the acute flush, 30d the sustained slide -- so the strongest of
    the three leads and the others confirm. A plain average of all three would
    punish a stock that collapsed this week but was flat the month before,
    which is exactly the setup worth finding.
    """
    windows = {
        "return_7d": low_is_good(r.get("return_7d", np.nan), -0.03, -0.18),
        "return_14d": low_is_good(r.get("return_14d", np.nan), -0.04, -0.25),
        "return_30d": low_is_good(r.get("return_30d", np.nan), -0.05, -0.32),
    }
    present = [v for v in windows.values() if not pd.isna(v)]
    if not present:
        return float("nan")
    strongest = max(present)
    rest = sorted(present, reverse=True)[1:]
    support = sum(rest) / len(rest) if rest else strongest
    return float(clamp(0.70 * strongest + 0.30 * support))


def technical_opportunity_score(r: pd.Series) -> dict[str, float]:
    """Score the opportunity itself, not whether the rebound has already started.

    Three dimensions that measure genuinely different things. The previous
    version averaged eight sub-signals of which six were near-duplicate
    measures of "the price is down" -- return_5d, return_20d, distance_sma20,
    distance_sma50, z_score and rsi_14 correlate between 0.75 and 0.87 on live
    data. Each was calibrated to a different extreme, so a stock had to hit all
    six extremes at once to score well. None ever did: across 228 tickers and
    113 recorded scans the component never once passed 68 out of 100, which
    capped the whole scanner regardless of its weights.
    """
    dislocation = {
        # How far it has fallen, over the windows where dip-buying pays.
        "drawdown": _drawdown_component(r),
        # How far it sits below where it has been, independent of the slide.
        "distance_52w_high": low_is_good(r.get("distance_52w_high", np.nan), -0.08, -0.50),
    }
    dislocation_weights = {"drawdown": 0.65, "distance_52w_high": 0.35}

    # Is the selling stretched, or is this an orderly decline with room to fall?
    exhaustion = {
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 45, 20),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.50, -2.50),
    }
    exhaustion_weights = {"rsi_14": 0.55, "z_score": 0.45}

    # Signs the fall is being absorbed rather than still accelerating.
    stabilisation = {
        "volume_ratio": _neutral_centered_high(r.get("volume_ratio", np.nan), 1.0, 3.0),
        "close_location": _neutral_centered_high(r.get("close_location", np.nan), 0.40, 0.90),
        "support": _technical_support_component(r),
        "sector_relative_strength_20d": _neutral_centered_high(r.get("sector_relative_strength_20d", np.nan), 0.0, 0.20),
    }
    stabilisation_weights = {
        "volume_ratio": 0.30,
        "close_location": 0.25,
        "support": 0.30,
        "sector_relative_strength_20d": 0.15,
    }

    dislocation_score = weighted_score(dislocation, dislocation_weights)
    exhaustion_score = weighted_score(exhaustion, exhaustion_weights)
    stabilisation_score = weighted_score(stabilisation, stabilisation_weights)

    # Dislocation sets the size of the opportunity; exhaustion and stabilisation
    # say whether to believe it. Those are not addable quantities, and averaging
    # them was what flattened the score: stabilisation sits near 50 for almost
    # every ticker, so as a weighted term it handed everyone the same points
    # instead of separating anything. As a multiplier it does its real job --
    # discounting a stock still in free fall without capping one that has fallen
    # hard and is being absorbed.
    confirmation = 0.60 * exhaustion_score + 0.40 * stabilisation_score
    confidence = CONFIRMATION_FLOOR + (CONFIRMATION_CEILING - CONFIRMATION_FLOOR) * clamp(confirmation / 100.0)
    total = min(100.0, dislocation_score * confidence)
    return {
        "technical_opportunity_score": float(total),
        "dislocation_score": float(dislocation_score),
        "exhaustion_score": float(exhaustion_score),
        "stabilisation_score": float(stabilisation_score),
        "confirmation_multiplier": float(confidence),
    }


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


def trader_setup_score(r: pd.Series) -> float:
    """Stable trader opportunity score from persistent price structure.

    The score is deliberately independent of the learned probability. The
    scanner should keep rating a stock highly while the opportunity remains:
    materially below its 52-week high, below key moving averages, oversold and
    near support. It should not lose 20-30 points simply because a classifier
    probability changed while the actual setup barely changed.
    """
    structural = {
        "drawdown_20d": low_is_good(r.get("return_20d", np.nan), -0.03, -0.35),
        "distance_52w_high": low_is_good(r.get("distance_52w_high", np.nan), -0.05, -0.45),
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 45, 22),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.30, -2.50),
        "distance_sma50": low_is_good(r.get("distance_sma50", np.nan), -0.03, -0.25),
        "support": _technical_support_component(r),
    }
    structural_weights = {
        "drawdown_20d": 0.20,
        "distance_52w_high": 0.45,
        "rsi_14": 0.10,
        "z_score": 0.03,
        "distance_sma50": 0.07,
        "support": 0.15,
    }
    confirmation = {
        "relative_strength_20d": _neutral_centered_high(r.get("relative_strength_20d", np.nan), 0.0, 0.15),
        "volume_ratio": _neutral_centered_high(r.get("volume_ratio", np.nan), 1.0, 3.0),
        "reversal": _neutral_centered_high(r.get("close_location", np.nan), 0.50, 1.00),
    }
    confirmation_weights = {
        "relative_strength_20d": 0.40,
        "volume_ratio": 0.30,
        "reversal": 0.30,
    }
    structural_score = weighted_score(structural, structural_weights)
    confirmation_score = weighted_score(confirmation, confirmation_weights)
    return float(0.90 * structural_score + 0.10 * confirmation_score)


def score_row(r: pd.Series, rebound_weights: dict, quality_weights: dict, cyclical_weights: dict) -> dict:
    rb = rebound_components(r)
    qu = quality_components(r)
    cy = cyclical_components(r)
    scores = {
        "rebound_score": weighted_score(rb, rebound_weights),
        "quality_score": weighted_score(qu, quality_weights),
        "cyclical_score": weighted_score(cy, cyclical_weights),
    }
    scores.update(technical_opportunity_score(r))
    scores["dip_score"] = dip_score(r)
    scores["reversal_trigger"] = reversal_trigger(r) * 100.0
    setup_key = max(["rebound_score", "quality_score", "cyclical_score"], key=lambda k: scores[k])

    trader = trader_setup_score(r)
    scores["trader_similarity_score"] = trader
    scores["trader_setup_score"] = trader
    scores["overall_score"] = 0.50 * trader + 0.50 * scores["technical_opportunity_score"]

    scores["watch_candidate"] = bool(
        scores["overall_score"] >= 65.0
        and trader >= 65.0
        and scores["technical_opportunity_score"] >= 60.0
        and scores["dip_score"] >= 55.0
    )
    scores["setup_type"] = "watch" if scores["watch_candidate"] else setup_key.replace("_score", "")
    return scores
