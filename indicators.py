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

    out["volatility_20d"] = out["return_1d"].rolling(20).std() * np.sqrt(252)
    out["z_score"] = (close - out["sma_20"]) / std20.replace(0, np.nan)

    rolling_high_252 = close.rolling(252, min_periods=20).max()
    out["high_52w"] = rolling_high_252
    out["distance_52w_high"] = close / rolling_high_252 - 1

    # Relative strength is calculated only from information available up to the row.
    if benchmark_close is not None:
        b = benchmark_close.reindex(out.index).ffill()
        benchmark_return20 = b.pct_change(20)
        out["relative_strength_20d"] = out["return_20d"] - benchmark_return20
    else:
        out["relative_strength_20d"] = np.nan

    return out
