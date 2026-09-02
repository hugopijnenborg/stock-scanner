from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df: pd.DataFrame, benchmark_close: pd.Series | None = None) -> pd.DataFrame:
    """Add causal technical features.

    Every feature only uses the current row and earlier rows. This is important
    because these features are later used both for historical backtests and
    live alerts.
    """
    out = df.copy().sort_index()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    volume = out["Volume"].astype(float)

    out["return_1d"] = close.pct_change(1)
    out["return_3d"] = close.pct_change(3)
    out["return_5d"] = close.pct_change(5)
    out["return_10d"] = close.pct_change(10)
    out["return_20d"] = close.pct_change(20)

    out["sma_20"] = close.rolling(20).mean()
    out["sma_50"] = close.rolling(50).mean()
    out["sma_200"] = close.rolling(200).mean()
    out["ema_20"] = close.ewm(span=20, adjust=False).mean()

    out["distance_sma20"] = close / out["sma_20"] - 1
    out["distance_sma50"] = close / out["sma_50"] - 1
    out["distance_sma200"] = close / out["sma_200"] - 1

    out["rsi_7"] = _rsi(close, 7)
    out["rsi_14"] = _rsi(close, 14)
    out["rsi_21"] = _rsi(close, 21)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_histogram"] = out["macd"] - out["macd_signal"]
    out["macd_histogram_change"] = out["macd_histogram"].diff()

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    out["atr_pct"] = out["atr_14"] / close

    std20 = close.rolling(20).std()
    out["bollinger_mid"] = out["sma_20"]
    out["bollinger_upper"] = out["sma_20"] + 2 * std20
    out["bollinger_lower"] = out["sma_20"] - 2 * std20
    band = (out["bollinger_upper"] - out["bollinger_lower"]).replace(0, np.nan)
    out["bollinger_pct"] = (close - out["bollinger_lower"]) / band
    out["bollinger_width"] = band / out["sma_20"]

    out["volume_avg20"] = volume.rolling(20).mean()
    out["volume_ratio"] = volume / out["volume_avg20"]
    out["volume_ratio_5d"] = volume / volume.rolling(5).mean()

    day_range = (high - low).replace(0, np.nan)
    out["close_location"] = (close - low) / day_range
    out["intraday_reversal"] = out["close_location"] - 0.5

    out["volatility_20d"] = out["return_1d"].rolling(20).std() * np.sqrt(252)
    out["z_score"] = (close - out["sma_20"]) / std20.replace(0, np.nan)

    for window, label in [(21, "1m"), (63, "3m"), (126, "6m"), (252, "52w")]:
        rolling_high = close.rolling(window, min_periods=min(window, 20)).max()
        out[f"high_{label}"] = rolling_high
        out[f"distance_{label}_high"] = close / rolling_high - 1

    for window, label in [(20, "20d"), (60, "60d"), (120, "120d")]:
        support = low.rolling(window, min_periods=min(window, 20)).min()
        out[f"support_{label}"] = support
        out[f"distance_support_{label}"] = close / support - 1

    if benchmark_close is not None:
        b = pd.to_numeric(benchmark_close, errors="coerce").reindex(out.index).ffill()
        benchmark_return5 = b.pct_change(5)
        benchmark_return20 = b.pct_change(20)
        benchmark_sma20 = b.rolling(20).mean()
        benchmark_sma50 = b.rolling(50).mean()
        out["relative_strength_20d"] = out["return_20d"] - benchmark_return20
        out["relative_strength_5d"] = out["return_5d"] - benchmark_return5

        # Market regime is intentionally causal. It measures broad-market
        # direction, trend alignment and recent return, rather than predicting
        # the future. 0 = hostile, 0.5 = neutral, 1 = supportive.
        trend20 = ((b / benchmark_sma20) - 1).clip(-0.10, 0.10)
        trend50 = ((b / benchmark_sma50) - 1).clip(-0.15, 0.15)
        regime_return = benchmark_return20.clip(-0.20, 0.20)
        trend20_score = ((trend20 + 0.10) / 0.20).fillna(0.5)
        trend50_score = ((trend50 + 0.15) / 0.30).fillna(0.5)
        return_score = ((regime_return + 0.20) / 0.40).fillna(0.5)
        out["market_regime_score"] = (0.40 * trend20_score + 0.40 * trend50_score + 0.20 * return_score).clip(0, 1)
    else:
        out["relative_strength_20d"] = np.nan
        out["relative_strength_5d"] = np.nan
        out["market_regime_score"] = 0.5

    return out
