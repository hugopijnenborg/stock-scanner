from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_START, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from model import score_row
from universe import load_top_us_stocks

HORIZONS = (5, 10, 20)
BANDS = ((80, 85, "80-84"), (85, 90, "85-89"), (90, 101, "90+"))


def _forward_return(close: pd.Series, dates: pd.DatetimeIndex, i: int, days: int) -> float | None:
    j = i + days
    if j >= len(dates):
        return None
    entry = float(close.iloc[i])
    if not np.isfinite(entry) or entry == 0:
        return None
    return float(close.iloc[j] / entry - 1.0)


def _signal_row(ticker: str, company: str, features: pd.DataFrame, i: int, spy: pd.Series | None) -> dict | None:
    row = features.iloc[i]
    score = score_row(row, REBOUND_WEIGHTS, QUALITY_WEIGHTS, CYCLICAL_WEIGHTS)
    overall = float(score["overall_score"])
    if overall < 80:
        return None

    dates = features.index
    result = {
        "date": dates[i].strftime("%Y-%m-%d"),
        "ticker": ticker,
        "company_name": company,
        "price": float(row["Close"]),
        "overall_score": round(overall, 2),
        "trader_similarity_score": round(float(score["trader_similarity_score"]), 2),
        "technical_score": round(float(score["technical_opportunity_score"]), 2),
        "setup_type": score["setup_type"],
    }
    for days in HORIZONS:
        result[f"return_{days}d"] = _forward_return(features["Close"], dates, i, days)

    end = min(i + 20, len(dates) - 1)
    future = features["Close"].iloc[i + 1 : end + 1]
    entry = float(row["Close"])
    result["max_gain_20d"] = float(future.max() / entry - 1) if len(future) else None
    result["max_drawdown_20d"] = float(future.min() / entry - 1) if len(future) else None

    if spy is not None:
        spy_aligned = spy.reindex(dates).ffill()
        result["spy_return_20d"] = _forward_return(spy_aligned, dates, i, 20)
    else:
        result["spy_return_20d"] = None
    return result


def _summarize(signals: pd.DataFrame) -> dict:
    summary = {"signals": int(len(signals))}
    if signals.empty:
        return summary

    for low, high, label in BANDS:
        part = signals[(signals["overall_score"] >= low) & (signals["overall_score"] < high)]
        item = {"signals": int(len(part))}
        for days in HORIZONS:
            values = pd.to_numeric(part[f"return_{days}d"], errors="coerce").dropna()
            item[f"avg_return_{days}d"] = float(values.mean()) if len(values) else None
            item[f"median_return_{days}d"] = float(values.median()) if len(values) else None
            item[f"win_rate_{days}d"] = float((values > 0).mean()) if len(values) else None
        gains = pd.to_numeric(part["max_gain_20d"], errors="coerce").dropna()
        item["avg_max_gain_20d"] = float(gains.mean()) if len(gains) else None
        summary[label] = item

    for days in HORIZONS:
        values = pd.to_numeric(signals[f"return_{days}d"], errors="coerce").dropna()
        summary[f"overall_{days}d"] = {
            "signals": int(len(values)),
            "avg_return": float(values.mean()) if len(values) else None,
            "median_return": float(values.median()) if len(values) else None,
            "win_rate": float((values > 0).mean()) if len(values) else None,
        }
    return summary


def run_market_validation(start: str = DEFAULT_START, cooldown_days: int = 20) -> tuple[pd.DataFrame, dict]:
    universe = load_top_us_stocks()
    tickers = universe["ticker"].tolist()
    companies = universe.set_index("ticker")["company_name"].to_dict()

    benchmarks = download_benchmarks(start)
    spy_df = benchmarks.get("SPY")
    spy_close = spy_df["Close"] if spy_df is not None and "Close" in spy_df.columns else None
    market = download_ohlcv(tickers, start)

    rows: list[dict] = []
    for ticker, prices in market.items():
        if prices.empty or "Close" not in prices.columns:
            continue
        features = add_indicators(prices, spy_close)
        last_signal_i = -10_000
        for i in range(len(features)):
            if i - last_signal_i <= cooldown_days:
                continue
            signal = _signal_row(ticker, companies.get(ticker, ticker), features, i, spy_close)
            if signal is not None:
                rows.append(signal)
                last_signal_i = i

    signals = pd.DataFrame(rows)
    if not signals.empty:
        signals = signals.sort_values(["date", "overall_score"], ascending=[False, False]).reset_index(drop=True)
    return signals, _summarize(signals)


def write_outputs(signals: pd.DataFrame, summary: dict, csv_path: str, json_path: str) -> None:
    signals.to_csv(csv_path, index=False)
    Path(json_path).write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    signals, summary = run_market_validation()
    print(json.dumps(summary, indent=2))
    write_outputs(signals, summary, "market_validation.csv", "market_validation.json")
