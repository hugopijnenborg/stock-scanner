from __future__ import annotations

import pandas as pd

from config import DEFAULT_START, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from model import score_row


def load_entries(path: str = "trader_data.csv") -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.tz_localize(None)
    return df


def forward_returns(close: pd.Series, entry_date: pd.Timestamp) -> dict:
    future = close[close.index > entry_date]
    result = {}
    for days in [1, 3, 5, 10, 20]:
        result[f"return_{days}d"] = float(future.iloc[days - 1] / close.loc[entry_date] - 1) if len(future) >= days else None
    if len(future):
        window = future.iloc[:20]
        result["max_gain_20d"] = float(window.max() / close.loc[entry_date] - 1)
        result["max_drawdown_20d"] = float(window.min() / close.loc[entry_date] - 1)
    else:
        result["max_gain_20d"] = None
        result["max_drawdown_20d"] = None
    return result


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
        # Match the trading session on or immediately before the supplied date.
        eligible = features.loc[features.index <= date]
        if eligible.empty:
            output.append({**entry.to_dict(), "data_available": False})
            continue
        row = eligible.iloc[-1]
        score = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
        close = features["Close"].astype(float)
        actual_entry_price = float(entry["price"])
        result = {**entry.to_dict(), "data_available": True, "matched_session": eligible.index[-1], "market_close": float(row["Close"]), "entry_vs_close": actual_entry_price / float(row["Close"]) - 1}
        result.update(score)
        # Future returns are measured from the user's stated entry price.
        future = close[close.index > eligible.index[-1]]
        for days in [1, 3, 5, 10, 20]:
            result[f"return_{days}d"] = float(future.iloc[days - 1] / actual_entry_price - 1) if len(future) >= days else None
        window = future.iloc[:20]
        result["max_gain_20d"] = float(window.max() / actual_entry_price - 1) if len(window) else None
        result["max_drawdown_20d"] = float(window.min() / actual_entry_price - 1) if len(window) else None
        output.append(result)
    return pd.DataFrame(output)


if __name__ == "__main__":
    df = run_backtest()
    print(df.to_string(index=False))
    df.to_csv("trader_backtest.csv", index=False)
