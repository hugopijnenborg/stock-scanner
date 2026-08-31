from __future__ import annotations

import time
from typing import Iterable

import pandas as pd
import yfinance as yf

from config import DEFAULT_START, BENCHMARKS


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance can return either (field, ticker) or (ticker, field).
        if df.columns.nlevels == 2:
            fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
            if any(str(x[0]) in fields for x in df.columns):
                df.columns = [x[0] for x in df.columns]
            else:
                df.columns = [x[1] for x in df.columns]
    df.columns = [str(c) for c in df.columns]
    return df


def download_ohlcv(tickers: Iterable[str], start: str = DEFAULT_START, end: str | None = None) -> dict[str, pd.DataFrame]:
    symbols = list(dict.fromkeys(tickers))
    if not symbols:
        return {}

    raw = yf.download(
        symbols,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    result: dict[str, pd.DataFrame] = {}
    if len(symbols) == 1:
        result[symbols[0]] = _flatten_columns(raw).dropna(how="all")
        return result

    for ticker in symbols:
        try:
            df = raw[ticker].copy()
        except KeyError:
            continue
        df = _flatten_columns(df).dropna(how="all")
        if not df.empty:
            result[ticker] = df
        time.sleep(0.01)
    return result


def download_benchmarks(start: str = DEFAULT_START, end: str | None = None) -> dict[str, pd.DataFrame]:
    return download_ohlcv(BENCHMARKS, start=start, end=end)
