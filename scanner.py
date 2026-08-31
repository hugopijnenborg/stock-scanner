from __future__ import annotations

import pandas as pd

from config import (
    ALERT_THRESHOLD,
    DEFAULT_START,
    MIN_AVG_DOLLAR_VOLUME,
    MIN_PRICE,
    REBOUND_WEIGHTS,
    QUALITY_WEIGHTS,
    CYCLICAL_WEIGHTS,
)
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks


FEATURE_COLUMNS = [
    "rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram",
    "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width",
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "distance_sma20", "distance_sma50", "distance_sma200",
    "distance_1m_high", "distance_3m_high", "distance_6m_high", "distance_52w_high",
    "distance_support_20d", "distance_support_60d", "distance_support_120d",
    "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score",
    "close_location", "relative_strength_5d", "relative_strength_20d",
]


def _signal_label(score: float) -> str:
    if score >= ALERT_THRESHOLD:
        return "ALERT"
    if score >= 75:
        return "WATCH"
    return "NO_SIGNAL"


def scan(limit: int = 1000, top_n: int = 25) -> pd.DataFrame:
    universe = load_top_us_stocks(limit)
    tickers = universe["ticker"].tolist()
    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None

    market = download_ohlcv(tickers, DEFAULT_START)
    rows = []
    for ticker, prices in market.items():
        if prices.empty or "Close" not in prices.columns:
            continue
        features = add_indicators(prices, benchmark_close)
        row = features.iloc[-1].copy()
        avg_dollar_volume = (features["Close"] * features["Volume"]).rolling(20).mean().iloc[-1]
        if row.get("Close", 0) < MIN_PRICE or (
            pd.notna(avg_dollar_volume) and avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME
        ):
            continue

        scores = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        result = {
            "ticker": ticker,
            "price": float(row["Close"]),
            "avg_dollar_volume_20d": float(avg_dollar_volume) if pd.notna(avg_dollar_volume) else None,
        }
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items()})
        result["signal"] = _signal_label(float(scores["overall_score"]))
        result.update({
            k: float(row[k]) if pd.notna(row[k]) else None
            for k in FEATURE_COLUMNS
            if k in row
        })
        rows.append(result)

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values(["overall_score", "reversal_trigger"], ascending=[False, False])
        .head(top_n)
        .reset_index(drop=True)
    )


if __name__ == "__main__":
    result = scan()
    print(result.to_string(index=False))
