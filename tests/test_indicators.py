import numpy as np
import pandas as pd

from indicators import add_indicators


def sample_prices(n=260):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    base = 100 + np.arange(n) * 0.1 + 2 * np.sin(np.arange(n) / 8)
    return pd.DataFrame(
        {
            "Open": base,
            "High": base + 1,
            "Low": base - 1,
            "Close": base + 0.25,
            "Volume": np.full(n, 1_000_000),
        },
        index=idx,
    )


def test_indicator_columns_exist():
    result = add_indicators(sample_prices())
    expected = [
        "rsi_14", "macd", "macd_signal", "macd_histogram", "atr_14",
        "atr_pct", "sma_20", "sma_50", "sma_200", "bollinger_pct",
        "bollinger_width", "volume_ratio", "volatility_20d", "z_score",
        "distance_52w_high", "relative_strength_20d",
    ]
    assert all(column in result.columns for column in expected)
    assert pd.notna(result["sma_200"].iloc[-1])
    assert pd.notna(result["rsi_14"].iloc[-1])


def test_rsi_range():
    result = add_indicators(sample_prices())
    valid = result["rsi_14"].dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()
