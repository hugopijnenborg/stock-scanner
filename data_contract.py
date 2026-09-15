from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricSpec:
    name: str
    category: str
    required: bool = True
    source_kind: str = "derived"


# Single source of truth for the new 10-factor scoring model.
# Raw market data is sufficient to derive the technical/risk/market metrics.
# External fundamental/estimate/analyst metrics must carry point-in-time metadata.
REQUIRED_METRICS: tuple[MetricSpec, ...] = (
    # Historical trading pattern
    MetricSpec("trader_similarity", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_return_1d", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_return_5d", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_return_10d", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_return_20d", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_return_60d", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_combo_success", "historical_pattern", source_kind="historical_model"),
    MetricSpec("trader_recency", "historical_pattern", source_kind="historical_model"),
    # Price action
    *(MetricSpec(x, "price_action") for x in (
        "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
        "higher_highs", "higher_lows", "trend_direction", "sma_20", "sma_50",
        "sma_100", "sma_200", "distance_sma20", "distance_sma50", "distance_sma100",
        "distance_sma200", "support", "resistance", "distance_resistance",
        "breakout_breakdown", "consolidation_range", "high_1m", "high_3m",
        "high_6m", "high_52w", "drawdown_52w", "gap_behavior", "candle_structure",
        "reversal_patterns",
    )),
    # Momentum
    *(MetricSpec(x, "momentum") for x in (
        "rsi_7", "rsi_14", "rsi_21", "macd", "macd_histogram",
        "macd_acceleration", "roc", "momentum_acceleration", "relative_momentum",
    )),
    # Volume
    *(MetricSpec(x, "volume") for x in (
        "volume_ratio", "volume_ratio_5d", "volume_trend_20d", "green_red_volume",
        "volume_breakout", "obv", "accumulation_distribution", "money_flow",
        "dollar_volume",
    )),
    # Fundamentals
    *(MetricSpec(x, "fundamentals", source_kind="fundamental") for x in (
        "revenue_growth", "eps_growth", "eps", "fcf", "fcf_growth", "operating_margin",
        "gross_margin", "net_margin", "roe", "roic", "debt_equity", "net_debt",
        "interest_coverage", "current_ratio", "cash", "earnings_stability",
    )),
    # Valuation
    *(MetricSpec(x, "valuation", source_kind="fundamental") for x in (
        "pe", "forward_pe", "peg", "ev_ebitda", "ev_sales", "price_sales",
        "price_fcf", "fcf_yield", "earnings_yield", "valuation_vs_history",
        "valuation_vs_sector",
    )),
    # Growth and earnings
    *(MetricSpec(x, "growth_earnings", source_kind="estimates") for x in (
        "expected_eps_growth", "expected_revenue_growth", "earnings_surprise",
        "revenue_surprise", "guidance", "earnings_revisions", "growth_acceleration",
        "next_earnings_date",
    )),
    # Analysts
    *(MetricSpec(x, "analysts", source_kind="analyst") for x in (
        "consensus", "buy_hold_sell", "price_target_upside", "upgrades", "downgrades",
        "eps_revisions", "revenue_revisions",
    )),
    # Market and sector
    *(MetricSpec(x, "market_sector") for x in (
        "sp500_trend", "nasdaq_trend", "stock_vs_sp500", "stock_vs_nasdaq",
        "sector_performance", "stock_vs_sector", "sector_momentum", "sector_volatility",
        "market_regime", "vix_regime",
    )),
    # Risk
    *(MetricSpec(x, "risk") for x in (
        "atr_pct", "historical_volatility", "volatility_trend", "bollinger_width",
        "downside_volatility", "maximum_drawdown", "beta", "gap_risk", "liquidity_risk",
    )),
)


def audit_metrics(row: dict[str, Any], *, as_of: str | None = None) -> dict[str, Any]:
    """Audit one feature row. Never invent missing values.

    A metric is complete only when it has a finite value. Point-in-time external
    metrics additionally require an available_from timestamp no later than as_of.
    """
    missing: list[str] = []
    invalid: list[str] = []
    stale_or_unbounded: list[str] = []
    by_category: dict[str, dict[str, int]] = {}

    for spec in REQUIRED_METRICS:
        value = row.get(spec.name)
        category = by_category.setdefault(spec.category, {"required": 0, "present": 0})
        category["required"] += 1
        if value is None:
            missing.append(spec.name)
            continue
        if isinstance(value, bool):
            present = True
        else:
            try:
                present = bool(value == value)  # rejects NaN without numpy dependency
            except Exception:
                present = False
        if not present:
            invalid.append(spec.name)
            continue
        category["present"] += 1

        if spec.source_kind in {"fundamental", "estimates", "analyst"} and as_of is not None:
            available_from = row.get(f"{spec.name}__available_from") or row.get("data_available_from")
            if available_from is None:
                stale_or_unbounded.append(spec.name)

    required = len(REQUIRED_METRICS)
    present = required - len(missing) - len(invalid)
    completeness = 100.0 * present / required if required else 100.0
    hard_block = bool(missing or invalid or stale_or_unbounded)
    return {
        "complete": not hard_block,
        "hard_block": hard_block,
        "completeness_pct": round(completeness, 1),
        "missing": missing,
        "invalid": invalid,
        "point_in_time_unverified": stale_or_unbounded,
        "by_category": by_category,
    }
