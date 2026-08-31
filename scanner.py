from __future__ import annotations

import pandas as pd

from config import (
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
        if row.get("Close", 0) < MIN_PRICE or pd.notna(avg_dollar_volume) and avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME:
            continue
        scores = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        result = {"ticker": ticker, "price": float(row["Close"]), "avg_dollar_volume_20d": float(avg_dollar_volume) if pd.notna(avg_dollar_volume) else None}
        result.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in scores.items()})
        result.update({k: float(row[k]) if pd.notna(row[k]) else None for k in ["rsi_14", "atr_pct", "return_5d", "return_20d", "z_score", "volume_ratio", "distance_52w_high", "relative_strength_20d"]})
        rows.append(result)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("overall_score", ascending=False).head(top_n).reset_index(drop=True)


if __name__ == "__main__":
    result = scan()
    print(result.to_string(index=False))
