from __future__ import annotations

import pandas as pd

from config import DEFAULT_START, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from model import score_row

TRADING_HORIZONS = [1, 3, 5, 10, 20, 30]


def load_entries(path: str = "trader_data.csv") -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.tz_localize(None)
    return df


def run_backtest(path: str = "trader_data.csv") -> pd.DataFrame:
    entries = load_entries(path)
    tickers = entries["ticker"].unique().tolist()
    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None
    prices = download_ohlcv(tickers, DEFAULT_START)

    output = []
    for _, entry in entries.iterrows():
        ticker = entry["ticker"]
        df = prices.get(ticker)
        if df is None or df.empty:
            output.append({**entry.to_dict(), "data_available": False})
            continue
        features = add_indicators(df, benchmark_close)
        date = pd.Timestamp(entry["date"])
        eligible = features.loc[features.index <= date]
        if eligible.empty:
            output.append({**entry.to_dict(), "data_available": False})
            continue
        row = eligible.iloc[-1]
        score = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        close = features["Close"].astype(float)
        actual_entry_price = float(entry["price"])
        result = {
            **entry.to_dict(),
            "data_available": True,
            "matched_session": eligible.index[-1],
            "market_close": float(row["Close"]),
            "entry_vs_close": actual_entry_price / float(row["Close"]) - 1,
        }
        result.update(score)
        future = close[close.index > eligible.index[-1]]
        for days in TRADING_HORIZONS:
            result[f"return_{days}d"] = float(future.iloc[days - 1] / actual_entry_price - 1) if len(future) >= days else None

        # 60D is explicitly 60 calendar days. Use the first available trading session on or after that date.
        entry_day = eligible.index[-1].normalize()
        index_dates = pd.DatetimeIndex(close.index).normalize()
        target_day = entry_day + pd.Timedelta(days=60)
        target_positions = [i for i, d in enumerate(index_dates) if d >= target_day]
        if target_positions:
            target_pos = target_positions[0]
            result["return_60d"] = float(close.iloc[target_pos] / actual_entry_price - 1)
            window = close.iloc[future.index.searchsorted(close.index[target_pos], side="right") - len(close.iloc[target_pos:]):] if False else close.iloc[len(close) - len(close.loc[close.index <= close.index[target_pos]]) + (len(close.loc[close.index <= eligible.index[-1]]) if len(close.loc[close.index <= eligible.index[-1]]) else 0):target_pos + 1]
            window = close.iloc[eligible.index.get_indexer([eligible.index[-1]])[0] + 1:target_pos + 1]
            result["max_gain_60d"] = float(window.max() / actual_entry_price - 1) if len(window) else None
            result["max_drawdown_60d"] = float(window.min() / actual_entry_price - 1) if len(window) else None
        else:
            result["return_60d"] = None
            result["max_gain_60d"] = None
            result["max_drawdown_60d"] = None
        output.append(result)
    return pd.DataFrame(output)


if __name__ == "__main__":
    df = run_backtest()
    print(df.to_string(index=False))
    df.to_csv("trader_backtest.csv", index=False)
