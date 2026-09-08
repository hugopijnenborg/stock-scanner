from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
from typing import Any

import numpy as np
import pandas as pd

# Decision engine weights. These are intentionally kept separate from the old
# trader/technical scanner score. The opportunity score is the new decision
# layer and the alert action is a separate hard-filter layer.
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


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


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


def _target_upside(row: dict[str, Any]) -> float | None:
    u = _f(row.get("analyst_target_upside"))
    if u is not None:
        return u
    cur = _f(row.get("analyst_target_current")) or _f(row.get("price"))
    mean = _f(row.get("analyst_target_mean"))
    if cur and mean:
        return mean / cur - 1.0
    return None


def score_technical(r: dict[str, Any]) -> tuple[float, float]:
    # Reward dislocation + exhaustion + actual reversal. Low RSI/TD-like
    # exhaustion alone never becomes the dominant signal.
    selloff = (
        0.30 * _negative_scale(r.get("return_1d"), -0.01, -0.15)
        + 0.30 * _negative_scale(r.get("return_5d"), -0.04, -0.30)
        + 0.20 * _negative_scale(r.get("return_20d"), -0.05, -0.40)
        + 0.20 * _negative_scale(r.get("distance_52w_high"), -0.05, -0.50)
    )
    rsi = _negative_scale(r.get("rsi_14"), 45, 20)
    volume = _positive_scale(r.get("volume_ratio"), 1.0, 4.0)
    support = 1.0 - _clamp(np.mean([
        _f(r.get("distance_support_20d"), 0.10),
        _f(r.get("distance_support_60d"), 0.10),
        _f(r.get("distance_support_120d"), 0.10),
    ]) / 0.10)
    support = _clamp(float(support))
    reversal = reversal_confirmation(r)
    trend = (
        0.45 * _clamp((_f(r.get("distance_sma20"), 0.0) + 0.20) / 0.40)
        + 0.35 * _clamp((_f(r.get("distance_sma50"), 0.0) + 0.25) / 0.50)
        + 0.20 * _clamp((_f(r.get("distance_sma200"), 0.0) + 0.30) / 0.60)
    )
    td_bonus = 0.0
    td_count = _f(r.get("td_setup_count")) or _f(r.get("td_countdown_count"))
    if td_count is not None and td_count >= 9 and reversal >= 0.55:
        td_bonus = 0.08
    score = 100.0 * _clamp(
        0.27 * selloff
        + 0.13 * rsi
        + 0.10 * volume
        + 0.08 * support
        + 0.25 * reversal
        + 0.12 * trend
        + 0.05 * _clamp((_f(r.get("sector_relative_strength_20d"), 0.0) + 0.20) / 0.40)
        + td_bonus
    )
    return score, reversal


def reversal_confirmation(r: dict[str, Any]) -> float:
    signals = []
    close_location = _f(r.get("close_location"))
    if close_location is not None:
        signals.append(_clamp((close_location - 0.45) / 0.55))
    one_day = _f(r.get("return_1d"))
    if one_day is not None:
        signals.append(_clamp((one_day + 0.15) / 0.20))
    macd_change = _f(r.get("macd_histogram_change"))
    hist = _f(r.get("macd_histogram"), 0.0)
    if macd_change is not None:
        signals.append(_clamp((macd_change + abs(hist or 0.0)) / (abs(hist or 0.0) + 1e-9)))
    intraday = _f(r.get("intraday_score"))
    if intraday is not None:
        signals.append(_clamp(intraday / 100.0))
    return float(np.mean(signals)) if signals else 0.0


def score_fundamentals(r: dict[str, Any]) -> float:
    if bool(r.get("thesis_broken")):
        return 0.0
    growth = 0.5 * _positive_scale(r.get("revenue_growth"), 0.0, 0.30) + 0.5 * _positive_scale(r.get("eps_growth"), 0.0, 0.40)
    quality = 0.35 * _positive_scale(r.get("gross_margin"), 0.20, 0.60) + 0.35 * _positive_scale(r.get("fcf_margin"), 0.0, 0.25) + 0.30 * _positive_scale(r.get("roe"), 0.10, 0.30)
    leverage = 1.0 - _clamp((_f(r.get("debt_equity"), 0.5) or 0.5) / 1.5)
    dilution = 1.0 - _norm(r.get("dilution_risk"), 0.0)
    return 100.0 * _clamp(0.45 * growth + 0.35 * quality + 0.12 * leverage + 0.08 * dilution)


def score_valuation(r: dict[str, Any]) -> float:
    pe = _f(r.get("pe"))
    fpe = _f(r.get("forward_pe"))
    peg = _f(r.get("peg"))
    pe_score = _clamp((35.0 - pe) / 25.0) if pe is not None and pe > 0 else 0.5
    fpe_score = _clamp((30.0 - fpe) / 22.0) if fpe is not None and fpe > 0 else 0.5
    peg_score = _clamp((2.0 - peg) / 1.5) if peg is not None and peg > 0 else 0.5
    target = _target_upside(r)
    fair = _clamp((target + 0.10) / 0.60) if target is not None else 0.5
    return 100.0 * (0.25 * pe_score + 0.25 * fpe_score + 0.20 * peg_score + 0.30 * fair)


def score_analysts(r: dict[str, Any]) -> float:
    consensus = _norm((_f(r.get("analyst_consensus_score"), 50.0) or 50.0) / 100.0)
    target = _clamp((_target_upside(r) + 0.10) / 0.60) if _target_upside(r) is not None else 0.5
    changes = _f(r.get("analyst_bullish_changes_30d"), 0.0) or 0.0
    bearish = _f(r.get("analyst_bearish_changes_30d"), 0.0) or 0.0
    revision = _clamp(0.5 + 0.08 * (changes - bearish))
    earnings_rev = revision
    revenue_rev = revision
    fresh = _clamp((_f(r.get("analyst_count"), 0.0) or 0.0) / 20.0)
    stale_penalty = _norm(r.get("analyst_cache_stale"), 0.0)
    raw = 0.25 * consensus + 0.20 * target + 0.20 * revision + 0.20 * earnings_rev + 0.10 * revenue_rev + 0.05 * fresh
    return 100.0 * _clamp(raw * (1.0 - 0.15 * stale_penalty))


def score_catalysts(r: dict[str, Any]) -> tuple[float, str | None, int | None]:
    # Only use information already present in the scanner output. No catalyst
    # is invented when the source does not provide one.
    days = None
    earnings = r.get("next_earnings_date")
    if earnings:
        try:
            dt = pd.Timestamp(earnings)
            now = pd.Timestamp.now(tz=dt.tz if dt.tzinfo else "UTC")
            days = max(0, int((dt - now).total_seconds() / 86400))
        except Exception:
            days = None
    if days is not None and days <= 45:
        return 75.0, "Volgende kwartaalcijfers", days
    if r.get("recent_news"):
        return 60.0, "Recente nieuwsflow beschikbaar", days
    return 40.0, None, days


def score_market_and_risk(r: dict[str, Any]) -> tuple[float, float, float, list[str]]:
    warnings = []
    institutional = 0.5
    if _f(r.get("institutional_sentiment")) is not None:
        institutional = _norm(r.get("institutional_sentiment"))
    sector = _f(r.get("sector_relative_strength_20d"))
    sector_score = _clamp((sector + 0.20) / 0.40) if sector is not None else 0.5
    market = _f(r.get("market_regime_score"))
    macro_sector = 0.55 * (market if market is not None else 0.5) + 0.45 * sector_score
    liquidity = 0.5
    dollar_volume = _f(r.get("avg_dollar_volume_20d"))
    if dollar_volume is not None:
        liquidity = _clamp((math.log10(max(dollar_volume, 1)) - 6.0) / 3.0)
    spread = _f(r.get("spread_quality"))
    if spread is not None:
        liquidity = 0.5 * liquidity + 0.5 * _norm(spread)
    if dollar_volume is not None and dollar_volume < 10_000_000:
        warnings.append("Liquiditeit is relatief laag")
    short_risk = _norm(r.get("short_interest_risk"), 0.0)
    liquidity_risk = _clamp(0.75 * liquidity + 0.25 * (1.0 - short_risk))
    return institutional * 100.0, macro_sector * 100.0, liquidity_risk * 100.0, warnings


def calculate_opportunity_score(components: dict[str, float], data_quality: float, thesis_broken: bool = False) -> float:
    score = sum((components[k] / 100.0) * w for k, w in WEIGHTS.items()) / 100.0 * 100.0
    score *= 0.90 + 0.10 * _clamp(data_quality)
    if thesis_broken:
        score = min(score, 55.0)
    return round(score, 1)


def scenario_data(r: dict[str, Any], score: float, reversal: float, analyst_score: float) -> list[dict[str, Any]]:
    target = _target_upside(r)
    if target is None:
        return []
    # The analyst target is the supplied independent upside anchor. Shorter
    # paths require a stronger setup and are capped so they cannot fabricate
    # a return target above the supplied 12-month upside.
    upside = max(0.0, target)
    confidence = _clamp(0.40 * score / 100.0 + 0.35 * reversal + 0.25 * analyst_score / 100.0)
    one_month = min(upside, 0.25) if upside >= 0.25 else upside
    three_month = min(upside, 0.50) if upside >= 0.50 else upside
    twelve_month = upside
    return [
        {"name": "25pct_1m", "return_pct": one_month, "probability": _clamp(0.15 + 0.45 * confidence), "horizon_days": 31},
        {"name": "50pct_3m", "return_pct": three_month, "probability": _clamp(0.12 + 0.48 * confidence), "horizon_days": 93},
        {"name": "100pct_12m", "return_pct": twelve_month, "probability": _clamp(0.10 + 0.55 * confidence), "horizon_days": 365},
    ]


def qualifying_paths(scenarios: list[dict[str, Any]]) -> list[str]:
    out = []
    for s in scenarios:
        rule = PATH_RULES[s["name"]]
        if s["return_pct"] >= rule["min_upside"] and s["horizon_days"] <= rule["max_days"] and s["probability"] >= rule["min_probability"]:
            out.append(s["name"])
    return out


def risk_reward(r: dict[str, Any], target: float | None) -> float | None:
    price = _f(r.get("price"))
    if not price or target is None or target <= 0:
        return None
    support_dist = _f(r.get("distance_support_20d"))
    stop = price * (1.0 + min(-0.05, support_dist if support_dist is not None else -0.05))
    risk = max(0.01 * price, price - stop)
    reward = max(0.0, target - price)
    return reward / risk if risk > 0 else None


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


def _load_previous() -> dict[str, dict[str, Any]]:
    path = Path("public/data/alert_history.json")
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("alerts", raw) if isinstance(raw, dict) else raw
        out = {}
        for item in items if isinstance(items, list) else []:
            ticker = item.get("ticker")
            if ticker:
                out[str(ticker).upper()] = item
        return out
    except Exception:
        return {}


def _action(score: float, reversal: float, dilution: float, leverage: float, paths: list[str], analyst_revision: float, r: dict[str, Any], previous: dict[str, Any] | None) -> tuple[str, list[str]]:
    reasons = []
    thesis_broken = bool(r.get("thesis_broken"))
    existing = bool(r.get("is_existing_position")) or previous is not None
    if thesis_broken:
        return ("EXIT" if existing else "NONE"), ["Thesis is gemarkeerd als gebroken"]
    if not paths:
        reasons.append("Geen return-pad voldoet aan de vereiste upside, horizon en kans")
    if _f(r.get("avg_dollar_volume_20d"), 0.0) is not None and (_f(r.get("avg_dollar_volume_20d"), 0.0) or 0.0) < 5_000_000:
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
    if score >= 85 and reversal >= 0.70 and analyst_revision >= 0.40:
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
    required = [r.get("price"), r.get("rsi_14"), r.get("revenue_growth"), r.get("analyst_consensus_score")]
    data_quality = sum(v is not None and _f(v) is not None for v in required) / len(required)
    target = _target_upside(r)
    scenarios = scenario_data(r, 0.0, reversal, analysts)
    score = calculate_opportunity_score(components, data_quality, bool(r.get("thesis_broken")))
    scenarios = scenario_data(r, score, reversal, analysts)
    paths = qualifying_paths(scenarios)
    dilution = _norm(r.get("dilution_risk"), 0.0)
    leverage = _clamp((_f(r.get("debt_equity"), 0.5) or 0.5) / 1.0)
    revision = _clamp(0.5 + 0.08 * ((_f(r.get("analyst_bullish_changes_30d"), 0.0) or 0.0) - (_f(r.get("analyst_bearish_changes_30d"), 0.0) or 0.0)))
    action, action_reasons = _action(score, reversal, dilution, leverage, paths, revision, r, previous)
    expected_return = target
    rr = risk_reward(r, (_f(r.get("analyst_target_mean"))))
    confidence = 100.0 * _clamp(0.45 * data_quality + 0.20 * reversal + 0.20 * analysts / 100.0 + 0.15 * (1.0 - dilution))
    price = _f(r.get("price"))
    prev_score = _f((previous or {}).get("score"))
    prev_price = _f((previous or {}).get("price"))
    score_delta = abs(score - prev_score) if prev_score is not None else None
    price_delta = abs(price / prev_price - 1.0) if price and prev_price else None
    material = previous is None or action not in {"NONE", "HOLD"} or (score_delta is not None and score_delta >= MATERIAL_SCORE_DELTA) or (price_delta is not None and price_delta >= MATERIAL_PRICE_DELTA)
    signal = "ALERT" if action == "BUY" else "WATCH" if score >= 70 else "NO_SIGNAL"
    reasons = list(action_reasons)
    if reversal >= 0.55: reasons.append("Er is daadwerkelijke reversal-confirmatie")
    if target is not None and target > 0.25: reasons.append(f"Analistentarget impliceert {target * 100:.1f}% upside")
    if catalyst_desc: reasons.append(catalyst_desc)
    return {
        "opportunity_score": score,
        "score_label": "EXCELLENT" if score >= 85 else "STRONG" if score >= 75 else "WATCH" if score >= 65 else "LOW",
        "component_scores": {k: round(v, 1) for k, v in components.items()},
        "action": action,
        "qualifies_new_buy": action == "BUY",
        "qualifying_paths": paths,
        "scenarios": scenarios,
        "expected_return": expected_return,
        "risk_reward": round(rr, 2) if rr is not None else None,
        "confidence": round(confidence, 1),
        "reasons": reasons[:8],
        "warnings": warnings,
        "reversal_confirmation": round(reversal, 3),
        "catalyst_description": catalyst_desc,
        "catalyst_nearest_days": catalyst_days,
        "trading_plan": trading_plan(r, (_f(r.get("analyst_target_mean")))),
        "data_quality": round(data_quality, 3),
        "material_change": bool(material),
        "previous_score": prev_score,
        "score_delta": round(score_delta, 1) if score_delta is not None else None,
        "price_delta": round(price_delta, 4) if price_delta is not None else None,
        "setup_type": "high-beta mean reversion" if technical >= fundamentals and reversal >= 0.55 else "quality/value pullback" if fundamentals >= technical else "structural growth" if fundamentals >= 60 else "structural deterioration / value trap",
    }


def apply_opportunity_engine(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return frame
    previous = _load_previous()
    out = frame.copy()
    evaluations = []
    for _, row in out.iterrows():
        evaluations.append(evaluate_row(row.to_dict(), previous.get(str(row.get("ticker", "")).upper())))
    for key in ["opportunity_score", "score_label", "action", "qualifies_new_buy", "expected_return", "risk_reward", "confidence", "reversal_confirmation", "catalyst_description", "catalyst_nearest_days", "data_quality", "material_change", "previous_score", "score_delta", "price_delta", "setup_type"]:
        out[key] = [e.get(key) for e in evaluations]
    for key in ["component_scores", "qualifying_paths", "scenarios", "reasons", "warnings", "trading_plan"]:
        out[key] = [e.get(key) for e in evaluations]
    for name in WEIGHTS:
        out[f"opportunity_{name}_score"] = [e["component_scores"][name] for e in evaluations]
    # The old signal is retained for backwards compatibility, but the new
    # decision layer is now authoritative for alerts and UI opportunity cards.
    out["signal"] = ["ALERT" if e["action"] == "BUY" else "WATCH" if e["opportunity_score"] >= 70 else "NO_SIGNAL" for e in evaluations]
    out["overall_score"] = out["opportunity_score"]
    out["alert_summary"] = [" ".join(e["reasons"][:3]) if e["action"] == "BUY" else None for e in evaluations]
    out = out.sort_values(["opportunity_score", "ticker"], ascending=[False, True]).reset_index(drop=True)
    return out
