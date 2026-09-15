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
    """Return a 0..100 technical setup score with market and sector context."""
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
        "drawdown_5d": 0.15, "rsi_14": 0.15, "distance_sma20": 0.05,
        "distance_sma50": 0.05, "drawdown_20d": 0.10, "z_score": 0.10,
        "volume_ratio": 0.10, "support": 0.10, "intraday_reversal": 0.05,
        "relative_strength_20d": 0.03, "sector_relative_strength_20d": 0.07,
        "market_regime": 0.05,
    }
    return {"technical_opportunity_score": weighted_score(c, weights)}


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
    scores["reversal_trigger"] = reversal_trigger(row) * 100.0
    setup_key = max(["rebound_score", "quality_score", "cyclical_score"], key=lambda k: scores[k])
    scores["setup_type"] = setup_key.replace("_score", "")

    learned = _learned_score(row)
    scores["trader_similarity_score"] = learned if learned is not None else scores["technical_opportunity_score"]
    scores["overall_score"] = (
        0.70 * scores["trader_similarity_score"] + 0.30 * scores["technical_opportunity_score"]
        if learned is not None else scores["technical_opportunity_score"]
    )
    return scores


# ===========================================================================
# New methodology: Technical (dislocation x confirmation) + Fundamentals +
# Valuation + Analyst direction, with Confidence and R/R as separate,
# non-blended checks. Replaces the trader-similarity approach above, which
# is left in place only so learn_model.py / walk_forward_validation.py /
# market_validation.py keep running without immediately breaking. Those
# three scripts now validate a DIFFERENT formula than the one below —
# they have not been updated to match, and their output should not be
# read as validation of this new scoring until they are.
# ===========================================================================

def _score_range(value, zero_point: float, full_point: float) -> float | None:
    """Map value linearly onto 0-100 between zero_point (-> 0) and full_point
    (-> 100). Returns None, never 0, when value is missing — callers must
    exclude None components and renormalize rather than treating unknown
    as the worst case."""
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    value = float(value)
    if full_point > zero_point:
        if value <= zero_point:
            return 0.0
        if value >= full_point:
            return 100.0
        return 100.0 * (value - zero_point) / (full_point - zero_point)
    else:
        if value >= zero_point:
            return 0.0
        if value <= full_point:
            return 100.0
        return 100.0 * (zero_point - value) / (zero_point - full_point)


def _weighted_or_none(components: dict, weights: dict) -> tuple[float | None, float]:
    """Weighted average over only the components that have a value.
    Returns (score, completeness) where completeness is the fraction of
    total weight that was actually available (1.0 = nothing missing)."""
    usable = [(k, w) for k, w in weights.items() if components.get(k) is not None]
    total_weight = sum(weights.values())
    if not usable or total_weight <= 0:
        return None, 0.0
    used_weight = sum(w for _, w in usable)
    score = sum(components[k] * w for k, w in usable) / used_weight
    return score, used_weight / total_weight


def _drawdown_leg(value, full_point: float) -> float | None:
    """value is a return like -0.18 (down 18%); full_point is the negative
    threshold (e.g. -0.18) at which this leg reaches 100."""
    if value is None or pd.isna(value):
        return None
    value = float(value)
    if value >= 0:
        return 0.0
    return float(np.clip(value / full_point, 0.0, 1.0)) * 100.0


def dislocation_score(r: pd.Series) -> float:
    """65% drawdown (7/14/30D, strongest window leads: 70% strongest +
    30% average of the other two) + 35% distance to the 52-week high."""
    legs = [
        _drawdown_leg(r.get("return_7d"), -0.18),
        _drawdown_leg(r.get("return_14d"), -0.25),
        _drawdown_leg(r.get("return_30d"), -0.32),
    ]
    legs = [v for v in legs if v is not None]
    drawdown = None
    if legs:
        strongest = max(legs)
        others = [v for v in legs if v != strongest]
        drawdown = 0.70 * strongest + 0.30 * (float(np.mean(others)) if others else strongest)
    high52 = _drawdown_leg(r.get("distance_52w_high"), -0.50)
    score, _ = _weighted_or_none({"drawdown": drawdown, "high52": high52}, {"drawdown": 0.65, "high52": 0.35})
    return score if score is not None else 0.0


def confirmation_score(r: pd.Series) -> float:
    """0-100. Turned into a 0.70-1.15 multiplier by the caller — a falling
    knife (low confirmation) drags the score down, a stabilizing move
    (high confirmation) lifts it."""
    components = {
        "rsi_14": low_is_good(r.get("rsi_14", np.nan), 50, 20),
        "z_score": low_is_good(r.get("z_score", np.nan), -0.5, -3.0),
        "volume_ratio": high_is_good(r.get("volume_ratio", np.nan), 1.0, 3.5),
        "support": _technical_support_component(r),
        "sector_strength": high_is_good(r.get("sector_relative_strength_20d", np.nan), 0.0, 0.20),
    }
    weights = {"rsi_14": 0.33, "z_score": 0.27, "volume_ratio": 0.18, "support": 0.18, "sector_strength": 0.09}
    return weighted_score(components, weights)


def new_technical_score(r: pd.Series) -> float:
    dislocation = dislocation_score(r)
    confirmation = confirmation_score(r)
    multiplier = 0.70 + (confirmation / 100.0) * 0.45  # 0.70 (falling knife) .. 1.15 (confirmed stabilization)
    return float(np.clip(dislocation * multiplier, 0.0, 100.0))


def fundamentals_score_v2(fund: dict | None) -> tuple[float | None, float]:
    if not fund:
        return None, 0.0
    components = {
        "revenue_growth": _score_range(fund.get("revenue_growth"), -0.05, 0.30),
        "eps_growth": _score_range(fund.get("eps_growth"), -0.10, 0.30),
        "fcf_margin": _score_range(fund.get("fcf_margin"), -0.05, 0.20),
        "net_margin": _score_range(fund.get("net_margin"), 0.0, 0.25),
        "gross_margin": _score_range(fund.get("gross_margin"), 0.20, 0.60),
        "roe": _score_range(fund.get("roe"), 0.0, 0.30),
        "debt_equity": _score_range(fund.get("debt_equity"), 2.0, 0.25),
    }
    weights = {
        "revenue_growth": 0.20, "eps_growth": 0.20, "fcf_margin": 0.20,
        "net_margin": 0.15, "gross_margin": 0.10, "roe": 0.10, "debt_equity": 0.05,
    }
    return _weighted_or_none(components, weights)


def valuation_score_v2(fund: dict | None) -> tuple[float | None, float]:
    """Forward P/E (sector-relative when available) + PEG. For
    loss-making companies (EPS <= 0), P/E and PEG are not meaningful —
    EV/Sales (sector context not applied here, absolute band only) takes
    the full weight instead, labeled explicitly rather than guessed."""
    if not fund:
        return None, 0.0
    eps = fund.get("eps")
    if eps is not None and eps <= 0:
        ev_sales = fund.get("ev_sales")
        score = _score_range(ev_sales, 12.0, 2.0)
        return score, (1.0 if score is not None else 0.0)

    pe_vs_sector = fund.get("pe_vs_sector")
    if pe_vs_sector is not None:
        pe_score = _score_range(pe_vs_sector, 1.75, 0.75)
    else:
        forward_pe = fund.get("forward_pe") if fund.get("forward_pe") is not None else fund.get("pe")
        pe_score = _score_range(forward_pe, 45.0, 12.0)
    peg_score = _score_range(fund.get("peg"), 3.0, 1.0)
    return _weighted_or_none({"pe": pe_score, "peg": peg_score}, {"pe": 0.60, "peg": 0.40})


def analyst_direction_score(analyst: dict | None) -> tuple[float | None, float]:
    """Net analyst grade upgrades vs downgrades in the last 30 days.

    Honest limitation: the original design called for this to be 60%
    grade-direction + 40% target-price-direction. yfinance's
    upgrades_downgrades data gives a COUNT of target changes but not
    their direction (up or down) — see analyst.py's target_changes_30d.
    Without direction, that second sub-metric can't be built separately,
    so this collapses to one signal (net grade actions) rather than
    pretending to combine two independent ones.
    """
    if not analyst:
        return None, 0.0
    bullish = analyst.get("analyst_bullish_changes_30d")
    bearish = analyst.get("analyst_bearish_changes_30d")
    if bullish is None and bearish is None:
        return None, 0.0
    net = (bullish or 0) - (bearish or 0)
    score = _score_range(net, -3, 3)
    return score, 1.0


def earnings_adjustment(analyst: dict | None) -> float:
    """+/-5 point nudge. Zero point at +8% surprise (the historical median
    — most companies beat, so 0% is not a meaningful "neutral" line).
    Fades linearly to 0 over 120 days. An extra -2.5 if earnings are due
    within 7 days (the current setup hasn't been tested against them
    yet)."""
    if not analyst:
        return 0.0
    adjustment = 0.0
    surprise = analyst.get("last_earnings_surprise_pct")
    if surprise is not None:
        s = float(np.clip(surprise, -60, 100))
        if s <= -7:
            magnitude = -5.0
        elif s >= 23:
            magnitude = 5.0
        elif s <= 8:
            magnitude = -5.0 * (8 - s) / 15.0
        else:
            magnitude = 5.0 * (s - 8) / 15.0
        decay = 1.0
        earnings_date = analyst.get("last_earnings_date")
        if earnings_date:
            try:
                dt = pd.Timestamp(earnings_date)
                if dt.tzinfo is None:
                    dt = dt.tz_localize("UTC")
                days_since = (pd.Timestamp.now(tz="UTC") - dt).days
                decay = float(np.clip(1.0 - days_since / 120.0, 0.0, 1.0))
            except Exception:
                decay = 1.0
        adjustment += magnitude * decay
    next_earnings = analyst.get("next_earnings_date")
    if next_earnings:
        try:
            dt = pd.Timestamp(next_earnings)
            if dt.tzinfo is None:
                dt = dt.tz_localize("UTC")
            days_out = (dt - pd.Timestamp.now(tz="UTC")).days
            if 0 <= days_out <= 7:
                adjustment -= 2.5
        except Exception:
            pass
    return float(np.clip(adjustment, -5.0, 5.0))


def confidence_score(fund_completeness: float, val_completeness: float, analyst_completeness: float,
                      technical_value: float | None, fundamentals_value: float | None) -> float:
    """data completeness x component agreement. Technical is always
    available (pure price data), so it always contributes full weight.

    Agreement is intentionally simple: do Technical and Fundamentals sit
    on the same side of their own midpoint (both > 50 or both < 50)?
    Disagreement is a real reason for caution (asks you to trust a setup
    where the two most-weighted components point opposite ways) but this
    is a coarse proxy, not a validated "reliability" measure."""
    data_completeness = (1.0 + fund_completeness + val_completeness + analyst_completeness) / 4.0
    if technical_value is not None and fundamentals_value is not None:
        agreement = 1.0 if (technical_value - 50) * (fundamentals_value - 50) >= 0 else 0.4
    else:
        agreement = 0.7
    return float(np.clip(data_completeness * agreement * 100.0, 0.0, 100.0))


def risk_reward(r: pd.Series) -> dict:
    """stop = tighter of (recent support, entry - 1.5xATR).
    target = nearest resistance (1M or 3M rolling high) above price.
    No historical-forward-return target is used — that would require
    validated backtest statistics that don't exist yet for this model;
    using an unvalidated number to set the bar for a validated-sounding
    R/R gate would be worse than being explicit that it's absent."""
    price = r.get("Close")
    if price is None or pd.isna(price):
        return {"stop": None, "target": None, "risk_reward": None}
    price = float(price)

    atr_pct = r.get("atr_pct")
    atr_stop = price - 1.5 * float(atr_pct) * price if pd.notna(atr_pct) else None
    support_candidates = [r.get("support_20d"), r.get("support_60d")]
    support_stop = max((float(s) for s in support_candidates if pd.notna(s)), default=None)
    stop_candidates = [s for s in (atr_stop, support_stop) if s is not None]
    stop = max(stop_candidates) if stop_candidates else None  # tighter of the two = higher stop

    resistance_candidates = [r.get("high_1m"), r.get("high_3m")]
    resistance = max((float(x) for x in resistance_candidates if pd.notna(x) and float(x) > price), default=None)
    target = resistance

    if stop is None or target is None or stop >= price:
        return {"stop": round(stop, 2) if stop is not None else None, "target": round(target, 2) if target is not None else None, "risk_reward": None}
    rr = (target - price) / (price - stop)
    return {"stop": round(stop, 2), "target": round(target, 2), "risk_reward": round(rr, 2)}


def assemble_new_score(row: pd.Series, fundamentals: dict | None, analyst: dict | None, bear_regime: bool) -> dict:
    technical = new_technical_score(row)
    fund_score, fund_completeness = fundamentals_score_v2(fundamentals)
    val_score, val_completeness = valuation_score_v2(fundamentals)
    analyst_score, analyst_completeness = analyst_direction_score(analyst)
    earnings_adj = earnings_adjustment(analyst)

    components = {"technical": technical, "fundamentals": fund_score, "valuation": val_score, "analyst": analyst_score}
    weights = {"technical": 0.55, "fundamentals": 0.30, "valuation": 0.10, "analyst": 0.05}
    overall, _ = _weighted_or_none(components, weights)
    if overall is None:
        overall = technical
    overall = float(np.clip(overall + earnings_adj, 0.0, 100.0))
    regime_multiplier = 0.8 if bear_regime else 1.0
    overall = round(overall * regime_multiplier, 1)

    confidence = confidence_score(fund_completeness, val_completeness, analyst_completeness, technical, fund_score)
    rr = risk_reward(row)

    fcf = fundamentals.get("fcf") if fundamentals else None
    debt_equity = fundamentals.get("debt_equity") if fundamentals else None
    gate_excluded = fcf is not None and fcf < 0 and debt_equity is not None and debt_equity > 1.5

    return {
        "technical_score_v2": round(technical, 1),
        "fundamentals_score_v2": round(fund_score, 1) if fund_score is not None else None,
        "valuation_score_v2": round(val_score, 1) if val_score is not None else None,
        "analyst_direction_score": round(analyst_score, 1) if analyst_score is not None else None,
        "earnings_adjustment": round(earnings_adj, 1),
        "overall_score_v2": overall,
        "confidence": round(confidence, 1),
        "risk_reward": rr["risk_reward"],
        "stop_level": rr["stop"],
        "target_level": rr["target"],
        "gate_excluded": gate_excluded,
        "regime_multiplier": regime_multiplier,
    }
