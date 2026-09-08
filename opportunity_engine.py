from __future__ import annotations

from pathlib import Path
import json
import math
from typing import Any

import numpy as np
import pandas as pd

ENGINE_VERSION = 4
WEIGHTS = {
    "technical": 30,
    "fundamentals": 20,
    "valuation": 10,
    "analysts": 15,
    "catalysts": 10,
    "institutional": 5,
    "macro_sector": 5,
    "liquidity_risk": 5,
}
NEW_BUY_SCORE_PREFERRED = 85.0
MATERIAL_SCORE_DELTA = 4.0
MATERIAL_PRICE_DELTA = 0.05
PATH_RULES = {
    "25pct_1m": {"min_upside": 0.25, "max_days": 31, "min_probability": 0.35},
    "50pct_3m": {"min_upside": 0.50, "max_days": 93, "min_probability": 0.35},
    "100pct_12m": {"min_upside": 1.00, "max_days": 365, "min_probability": 0.30},
}


def _f(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(np.clip(x, lo, hi))


def _norm(v: Any, default: float = 0.5) -> float:
    x = _f(v)
    return default if x is None else _clamp(x)


def _positive_scale(v: Any, start: float, strong: float) -> float:
    x = _f(v)
    if x is None:
        return 0.5
    if x <= start:
        return 0.0
    return _clamp((x - start) / (strong - start))


def _negative_scale(v: Any, start: float, extreme: float) -> float:
    x = _f(v)
    if x is None:
        return 0.5
    if x >= start:
        return 0.0
    return _clamp((start - x) / (start - extreme))


def _target_upside(r: dict[str, Any]) -> float | None:
    u = _f(r.get("analyst_target_upside"))
    if u is not None:
        return u
    cur = _f(r.get("analyst_target_current")) or _f(r.get("price"))
    mean = _f(r.get("analyst_target_mean"))
    return mean / cur - 1.0 if cur and mean else None


def _recent_dislocation(r: dict[str, Any]) -> float:
    """How much the stock has actually sold off recently.

    Positive recent momentum must not count as reversal confirmation by itself.
    """
    return _clamp(
        0.30 * _negative_scale(r.get("return_1d"), -0.01, -0.15)
        + 0.30 * _negative_scale(r.get("return_5d"), -0.04, -0.30)
        + 0.20 * _negative_scale(r.get("return_20d"), -0.05, -0.40)
        + 0.20 * _negative_scale(r.get("distance_52w_high"), -0.05, -0.50)
    )


def reversal_confirmation(r: dict[str, Any]) -> float:
    """Measure reversal after dislocation, not simple positive momentum."""
    dislocation = _recent_dislocation(r)
    if dislocation <= 0.05:
        return 0.0

    signals: list[float] = []
    close = _f(r.get("close_location"))
    one_day = _f(r.get("return_1d"))
    five_day = _f(r.get("return_5d"))
    macd_change = _f(r.get("macd_histogram_change"))
    hist = _f(r.get("macd_histogram"), 0.0) or 0.0
    intraday = _f(r.get("intraday_score"))

    if close is not None:
        signals.append(_clamp((close - 0.50) / 0.50))
    if one_day is not None:
        signals.append(_clamp((one_day - 0.005) / 0.075))
    if five_day is not None:
        signals.append(_clamp((five_day + 0.10) / 0.20))
    if macd_change is not None:
        scale = max(abs(hist), 0.01)
        signals.append(_clamp(0.5 + macd_change / (2.0 * scale)))
    if intraday is not None:
        signals.append(_clamp((intraday - 50.0) / 50.0))

    bounce = float(np.mean(signals)) if signals else 0.0
    return round(_clamp(dislocation * bounce), 4)


def score_technical(r: dict[str, Any]) -> tuple[float, float]:
    selloff = _recent_dislocation(r)
    rsi = _negative_scale(r.get("rsi_14"), 45.0, 20.0)
    volume = _positive_scale(r.get("volume_ratio"), 1.0, 4.0)
    support_values = [
        _f(r.get("distance_support_20d")),
        _f(r.get("distance_support_60d")),
        _f(r.get("distance_support_120d")),
    ]
    support_values = [x for x in support_values if x is not None]
    support = 1.0 - _clamp(float(np.mean(support_values)) / 0.10) if support_values else 0.5
    reversal = reversal_confirmation(r)

    # Trend is deliberately neutral unless the stock is actually in a pullback.
    # A stock being above its moving averages is not itself an opportunity signal.
    d20 = _f(r.get("distance_sma20"))
    d50 = _f(r.get("distance_sma50"))
    d200 = _f(r.get("distance_sma200"))
    pullback_structure = 0.5
    if d20 is not None or d50 is not None or d200 is not None:
        values = [x for x in (d20, d50, d200) if x is not None]
        pullback_structure = _clamp(np.mean([_negative_scale(x, -0.02, -0.30) for x in values]))

    sector = _clamp((_f(r.get("sector_relative_strength_20d"), 0.0) + 0.20) / 0.40)
    td = _f(r.get("td_setup_count")) or _f(r.get("td_countdown_count")) or 0
    td_bonus = 0.08 if td >= 9 and reversal >= 0.55 else 0.0

    raw = (
        0.27 * selloff
        + 0.13 * rsi
        + 0.10 * volume
        + 0.08 * support
        + 0.25 * reversal
        + 0.12 * pullback_structure
        + 0.05 * sector
        + td_bonus
    )
    return 100.0 * _clamp(raw), reversal


def score_fundamentals(r: dict[str, Any]) -> float:
    if bool(r.get("thesis_broken")):
        return 0.0
    growth = 0.5 * _positive_scale(r.get("revenue_growth"), 0.0, 0.30) + 0.5 * _positive_scale(r.get("eps_growth"), 0.0, 0.40)
    quality = (
        0.35 * _positive_scale(r.get("gross_margin"), 0.20, 0.60)
        + 0.35 * _positive_scale(r.get("fcf_margin"), 0.0, 0.25)
        + 0.30 * _positive_scale(r.get("roe"), 0.10, 0.30)
    )
    leverage_raw = _f(r.get("debt_equity"))
    leverage = 0.5 if leverage_raw is None else 1.0 - _clamp(leverage_raw / 1.5)
    dilution = 1.0 - _norm(r.get("dilution_risk"), 0.0)
    return 100.0 * _clamp(0.45 * growth + 0.35 * quality + 0.12 * leverage + 0.08 * dilution)


def _relative_value_score(value: float | None, good: float, bad: float) -> float | None:
    if value is None or value <= 0:
        return None
    return _clamp((bad - value) / (bad - good))


def score_valuation(r: dict[str, Any]) -> float:
    parts: list[tuple[float, float]] = []
    pe = _f(r.get("pe"))
    fpe = _f(r.get("forward_pe"))
    peg = _f(r.get("peg"))
    pe_score = _relative_value_score(_f(r.get("pe_vs_sector")), 0.75, 1.75) if r.get("pe_vs_sector") is not None else _relative_value_score(pe, 15.0, 60.0)
    fpe_score = _relative_value_score(_f(r.get("forward_pe_vs_sector")), 0.75, 1.75) if r.get("forward_pe_vs_sector") is not None else _relative_value_score(fpe, 12.0, 55.0)
    peg_score = _relative_value_score(_f(r.get("peg_vs_sector")), 0.75, 1.75) if r.get("peg_vs_sector") is not None else _relative_value_score(peg, 1.0, 3.0)
    for value, weight in ((pe_score, 0.35), (fpe_score, 0.35), (peg_score, 0.30)):
        if value is not None:
            parts.append((value, weight))
    if not parts:
        return 50.0
    total = sum(w for _, w in parts)
    return 100.0 * sum(v * w for v, w in parts) / total


def _direction_score(value: Any, neutral: float = 0.5) -> float:
    if value is None:
        return neutral
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"strongly positive", "strong positive", "very bullish"}:
            return 1.0
        if s in {"positive", "bullish", "upgrade", "upgraded", "up"}:
            return 0.75
        if s in {"negative", "bearish", "downgrade", "downgraded", "down"}:
            return 0.25
        if s in {"strongly negative", "strong negative", "very bearish"}:
            return 0.0
        return neutral
    return _clamp(float(value))


def score_analysts(r: dict[str, Any]) -> float:
    consensus_raw = _f(r.get("analyst_consensus_score"))
    consensus = _clamp(consensus_raw / 100.0) if consensus_raw is not None else 0.5
    target_upside = _target_upside(r)
    target = _clamp((target_upside + 0.10) / 0.60) if target_upside is not None else 0.5
    target_revision = _direction_score(r.get("target_revision_direction"))
    earnings_revision = _direction_score(r.get("earnings_revision_direction"))
    revenue_revision = _direction_score(r.get("revenue_revision_direction"))
    if r.get("target_revision_direction") is None:
        bullish = _f(r.get("analyst_bullish_changes_30d"), 0.0) or 0.0
        bearish = _f(r.get("analyst_bearish_changes_30d"), 0.0) or 0.0
        target_revision = _clamp(0.5 + 0.08 * (bullish - bearish))
    count = _f(r.get("analyst_count"), 0.0) or 0.0
    freshness = _clamp(count / 20.0)
    stale = _norm(r.get("analyst_cache_stale"), 0.0)
    raw = 0.25 * consensus + 0.20 * target + 0.20 * target_revision + 0.20 * earnings_revision + 0.10 * revenue_revision + 0.05 * freshness
    return 100.0 * _clamp(raw * (1.0 - 0.15 * stale))


def score_catalysts(r: dict[str, Any]) -> tuple[float, str | None, int | None]:
    days = None
    earnings = r.get("next_earnings_date")
    if earnings:
        try:
            dt = pd.Timestamp(earnings)
            now = pd.Timestamp.now(tz=dt.tz if dt.tzinfo else "UTC")
            days = max(0, int((dt - now).total_seconds() / 86400))
        except Exception:
            days = None
    strength_values = [_f(r.get("one_month_strength")), _f(r.get("three_month_strength")), _f(r.get("twelve_month_strength"))]
    supplied = [x for x in strength_values if x is not None]
    if supplied:
        return 100.0 * float(np.mean([_clamp(x) for x in supplied])), _clean_catalyst_text(r.get("catalyst_description")), days
    if days is not None and days <= 45:
        return 75.0, "Volgende kwartaalcijfers", days
    if r.get("recent_news"):
        return 60.0, "Recente nieuwsflow beschikbaar", days
    return 40.0, None, days


def _clean_catalyst_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def score_market_and_risk(r: dict[str, Any]) -> tuple[float, float, float, list[str]]:
    warnings: list[str] = []
    institutional = _norm(r.get("institutional_sentiment"), 0.5)
    sector = _f(r.get("sector_relative_strength_20d"))
    sector_score = _clamp((sector + 0.20) / 0.40) if sector is not None else 0.5
    market = _f(r.get("market_regime_score"))
    macro = 0.55 * (market if market is not None else 0.5) + 0.45 * sector_score
    dollar = _f(r.get("avg_dollar_volume_20d"))
    liquidity = _clamp((math.log10(max(dollar, 1)) - 6.0) / 3.0) if dollar is not None else 0.5
    spread = _f(r.get("spread_quality"))
    if spread is not None:
        liquidity = 0.5 * liquidity + 0.5 * _norm(spread)
    if dollar is not None and dollar < 10_000_000:
        warnings.append("Liquiditeit is relatief laag")
    short_risk = _norm(r.get("short_interest_risk"), 0.0)
    liquidity_risk = _clamp(0.75 * liquidity + 0.25 * (1.0 - short_risk))
    return institutional * 100.0, macro * 100.0, liquidity_risk * 100.0, warnings


def _component_data_quality(r: dict[str, Any]) -> float:
    groups = [
        ["return_1d", "return_5d", "return_20d", "distance_52w_high", "rsi_14", "volume_ratio", "close_location", "macd_histogram_change", "intraday_score"],
        ["revenue_growth", "eps_growth", "gross_margin", "fcf_margin", "roe", "debt_equity", "fcf"],
        ["pe", "forward_pe", "peg", "pe_vs_sector", "forward_pe_vs_sector", "peg_vs_sector"],
        ["analyst_consensus_score", "analyst_target_mean", "analyst_count"],
    ]
    available = sum(1 for group in groups for key in group if _f(r.get(key)) is not None)
    total = sum(len(group) for group in groups)
    return _clamp(available / total)


def calculate_opportunity_score(components: dict[str, float], data_quality: float, thesis_broken: bool = False) -> float:
    score = sum((components[k] / 100.0) * WEIGHTS[k] for k in WEIGHTS)
    score *= 0.90 + 0.10 * _clamp(data_quality)
    if thesis_broken:
        score = min(score, 55.0)
    return round(score, 1)


def scenario_data(r: dict[str, Any], score: float, reversal: float, analyst_score: float) -> list[dict[str, Any]]:
    # Explicit scenarios are preferred. Do not manufacture a probability from an analyst target.
    supplied = r.get("scenarios")
    if isinstance(supplied, list):
        return [s for s in supplied if isinstance(s, dict) and s.get("name") in PATH_RULES]
    return []


def qualifying_paths(scenarios: list[dict[str, Any]]) -> list[str]:
    paths = []
    for s in scenarios:
        try:
            name = s["name"]
            rule = PATH_RULES[name]
            if float(s.get("return_pct", 0)) >= rule["min_upside"] and float(s.get("horizon_days", 9999)) <= rule["max_days"] and float(s.get("probability", 0)) >= rule["min_probability"]:
                paths.append(name)
        except (KeyError, TypeError, ValueError):
            continue
    return paths


def trading_plan(r: dict[str, Any], target: float | None) -> dict[str, Any]:
    price = _f(r.get("price")) or 0.0
    atr = _f(r.get("atr_pct"), 0.06) or 0.06
    entry_low = price * (1.0 - min(0.08, max(0.02, atr * 0.5)))
    entry_high = price * (1.0 + min(0.02, max(0.005, atr * 0.15)))
    add_low = price * (1.0 - min(0.12, max(0.04, atr)))
    add_high = entry_low
    invalidation = price * (1.0 - min(0.18, max(0.07, atr * 1.5)))
    tp1 = price * 1.25 if target is None else min(target, price * 1.25) if target > price else price * 1.15
    tp2 = price * 1.50 if target is None else target if target > price else price * 1.25
    return {"entry_low": entry_low, "entry_high": entry_high, "add_low": add_low, "add_high": add_high, "invalidation": invalidation, "tp1": tp1, "tp2": tp2}


def risk_reward(r: dict[str, Any], target: float | None) -> float | None:
    price = _f(r.get("price"))
    if not price or target is None or target <= 0:
        return None
    support_dist = _f(r.get("distance_support_20d"))
    stop = price * (1.0 + min(-0.05, support_dist if support_dist is not None else -0.05))
    risk = max(0.01 * price, price - stop)
    reward = max(0.0, target - price)
    return reward / risk if risk > 0 else None


def _load_previous() -> dict[str, dict[str, Any]]:
    path = Path("public/data/alert_history.json")
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("alerts", raw) if isinstance(raw, dict) else raw
        return {str(x.get("ticker")).upper(): x for x in items if isinstance(x, dict) and x.get("ticker")}
    except Exception:
        return {}


def _classify_setup(technical: float, fundamentals: float, valuation: float, reversal: float, r: dict[str, Any]) -> str:
    if bool(r.get("thesis_broken")) or (fundamentals < 35 and valuation < 45):
        return "structural deterioration / value trap"
    if reversal >= 0.55 and technical >= 70:
        return "high-beta mean reversion"
    if fundamentals >= 70 and valuation >= 60 and technical < 65:
        return "quality/value pullback"
    if fundamentals >= 70:
        return "structural growth"
    if valuation >= 70 and fundamentals >= 55:
        return "quality/value pullback"
    return "structural growth" if fundamentals >= technical else "high-beta mean reversion"


def _action(score: float, reversal: float, dilution: float, leverage: float, paths: list[str], revision: float, r: dict[str, Any], previous: dict[str, Any] | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    existing = bool(r.get("is_existing_position")) or previous is not None
    if r.get("thesis_broken"):
        return ("EXIT" if existing else "NONE"), ["Thesis is gemarkeerd als gebroken"]
    if not paths:
        reasons.append("Geen return-pad voldoet aan de vereiste upside, horizon en kans")
    volume = _f(r.get("avg_dollar_volume_20d"), 0.0) or 0.0
    if volume < 5_000_000:
        return "NONE", reasons + ["Liquiditeit onder de scannergrens"]
    if not existing:
        if score >= NEW_BUY_SCORE_PREFERRED and paths and reversal >= 0.55 and dilution <= 0.75 and leverage <= 0.85:
            return "BUY", reasons + ["Score, reversal, return-pad, leverage en dilution voldoen aan de BUY-filters"]
        return "NONE", reasons
    price = _f(r.get("price"), 0.0) or 0.0
    plan = trading_plan(r, _f(r.get("analyst_target_mean")))
    if score < 60:
        return "EXIT", reasons + ["Opportunity score onder 60"]
    if price >= plan["tp2"]:
        return "TAKE PROFIT", reasons + ["TP2 bereikt"]
    if price >= plan["tp1"] or (_f(r.get("rsi_14"), 0.0) or 0.0) >= 75:
        return "PARTIAL TAKE PROFIT", reasons + ["Setup is overextended of TP1 bereikt"]
    if score >= 85 and reversal >= 0.70 and revision >= 0.40:
        return "ADD", reasons + ["Sterke score, reversal en analistenrevisies"]
    return "HOLD", reasons + ["Bestaande positie blijft binnen de actieband"]


def evaluate_row(row: Any, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    r = dict(row)
    technical, reversal = score_technical(r)
    fundamentals = score_fundamentals(r)
    valuation = score_valuation(r)
    analysts = score_analysts(r)
    catalysts, catalyst_desc, catalyst_days = score_catalysts(r)
    institutional, macro_sector, liquidity_risk, warnings = score_market_and_risk(r)
    components = {
        "technical": technical,
        "fundamentals": fundamentals,
        "valuation": valuation,
        "analysts": analysts,
        "catalysts": catalysts,
        "institutional": institutional,
        "macro_sector": macro_sector,
        "liquidity_risk": liquidity_risk,
    }
    data_quality = _component_data_quality(r)
    score = calculate_opportunity_score(components, data_quality, bool(r.get("thesis_broken")))
    target = _target_upside(r)
    scenarios = scenario_data(r, score, reversal, analysts)
    paths = qualifying_paths(scenarios)
    dilution = _norm(r.get("dilution_risk"), 0.0)
    leverage_raw = _f(r.get("debt_equity"))
    leverage = _clamp(leverage_raw / 1.0) if leverage_raw is not None else 0.5
    bullish = _f(r.get("analyst_bullish_changes_30d"), 0.0) or 0.0
    bearish = _f(r.get("analyst_bearish_changes_30d"), 0.0) or 0.0
    revision = _direction_score(r.get("target_revision_direction")) if r.get("target_revision_direction") is not None else _clamp(0.5 + 0.08 * (bullish - bearish))
    action, action_reasons = _action(score, reversal, dilution, leverage, paths, revision, r, previous)
    rr = risk_reward(r, _f(r.get("analyst_target_mean")))
    confidence = 100.0 * _clamp(0.45 * data_quality + 0.20 * reversal + 0.20 * analysts / 100.0 + 0.15 * (1.0 - dilution))
    price = _f(r.get("price"))
    prev_score = _f((previous or {}).get("opportunity_score")) or _f((previous or {}).get("score"))
    prev_price = _f((previous or {}).get("price"))
    score_delta = abs(score - prev_score) if prev_score is not None else None
    price_delta = abs(price / prev_price - 1.0) if price and prev_price else None
    material = previous is None or action not in {"NONE", "HOLD"} or (score_delta is not None and score_delta >= MATERIAL_SCORE_DELTA) or (price_delta is not None and price_delta >= MATERIAL_PRICE_DELTA)
    reasons = list(action_reasons)
    if reversal >= 0.55:
        reasons.append("Er is daadwerkelijke reversal-confirmatie")
    if target is not None and target > 0.25:
        reasons.append(f"Analistentarget impliceert {target * 100:.1f}% upside")
    if catalyst_desc:
        reasons.append(catalyst_desc)
    setup = _classify_setup(technical, fundamentals, valuation, reversal, r)
    score_breakdown = {k: round(components[k] * WEIGHTS[k] / 100.0, 2) for k in WEIGHTS}
    should_alert = bool(action != "NONE" and action != "HOLD" and material)
    return {
        "opportunity_score": score,
        "score_label": "EXCELLENT" if score >= 85 else "STRONG" if score >= 75 else "WATCH" if score >= 65 else "LOW",
        "component_scores": {k: round(v, 1) for k, v in components.items()},
        "score_breakdown": score_breakdown,
        "action": action,
        "qualifies_new_buy": action == "BUY",
        "should_alert": should_alert,
        "qualifying_paths": paths,
        "scenarios": scenarios,
        "expected_return": target,
        "risk_reward": round(rr, 2) if rr is not None else None,
        "confidence": round(confidence, 1),
        "reasons": reasons[:8],
        "warnings": warnings,
        "reversal_confirmation": round(reversal, 3),
        "catalyst_description": catalyst_desc,
        "catalyst_nearest_days": catalyst_days,
        "trading_plan": trading_plan(r, _f(r.get("analyst_target_mean"))),
        "data_quality": round(data_quality, 3),
        "material_change": bool(material),
        "previous_score": prev_score,
        "score_delta": round(score_delta, 1) if score_delta is not None else None,
        "price_delta": round(price_delta, 4) if price_delta is not None else None,
        "setup_type": setup,
    }


def apply_opportunity_engine(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame
    previous = _load_previous()
    out = frame.copy()
    evaluations = [evaluate_row(row.to_dict(), previous.get(str(row.get("ticker", "")).upper())) for _, row in out.iterrows()]
    scalar_keys = [
        "opportunity_score", "score_label", "action", "qualifies_new_buy", "should_alert", "expected_return", "risk_reward", "confidence",
        "reversal_confirmation", "catalyst_description", "catalyst_nearest_days", "data_quality", "material_change", "previous_score", "score_delta", "price_delta", "setup_type",
    ]
    for key in scalar_keys:
        out[key] = [e.get(key) for e in evaluations]
    for key in ["component_scores", "score_breakdown", "qualifying_paths", "scenarios", "reasons", "warnings", "trading_plan"]:
        out[key] = [e.get(key) for e in evaluations]
    for name in WEIGHTS:
        out[f"opportunity_{name}_score"] = [e["component_scores"][name] for e in evaluations]
        out[f"opportunity_{name}_weighted"] = [e["score_breakdown"][name] for e in evaluations]
    return out.sort_values(["opportunity_score", "ticker"], ascending=[False, True]).reset_index(drop=True)
