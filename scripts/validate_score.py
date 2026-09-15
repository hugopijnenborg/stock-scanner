"""Does a high score actually predict a higher forward return?

Nothing in the scanner answered that. The alert table holds a handful of rows,
all from retired models, and market_validation.py discards everything below 80,
so there was never a control group: no way to tell whether a scoring 85 beats a
scoring 40, or whether the ranking is noise.

This rebuilds the price-derived half of the score for every ticker on every
sampled trading day over a multi-year window and measures what happened next.
Roughly a hundred thousand observations instead of a handful.

Fundamentals are deliberately excluded. Only their current values are
available, so using them here would score 2024 with 2026 balance sheets --
look-ahead bias that flatters any result it touches. What this validates is
trader and technical, 65% of the production weight and the part that was
rebuilt. Fundamentals stay on reasoning until the scan log has enough history.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# Run as `python scripts/validate_score.py` and Python puts scripts/ on the
# path, not the repository root, so the project modules below are invisible.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from config import DEFAULT_START
from data import download_benchmarks, download_ohlcv, download_sector_benchmarks, SECTOR_ETFS
from indicators import add_indicators
from main import MODEL_VERSION
from model import new_technical_score
from universe import load_top_us_stocks

HORIZONS = (5, 10, 20)
DECILES = 10


def _sector_relative_series(close: pd.Series, sector_close: pd.Series | None) -> pd.Series:
    """20-day return minus the sector ETF's, as a series so every day is scored.

    scanner.py computes this for the latest bar only; a historical run needs the
    value the scanner would have seen on each past day.
    """
    if sector_close is None or len(sector_close) < 21:
        return pd.Series(np.nan, index=close.index)
    aligned = pd.to_numeric(sector_close, errors="coerce").reindex(close.index).ffill()
    return close.pct_change(20) - aligned.pct_change(20)


def _forward(close: pd.Series, i: int, days: int) -> float | None:
    j = i + days
    if j >= len(close):
        return None
    entry = float(close.iloc[i])
    if not np.isfinite(entry) or entry == 0:
        return None
    nxt = float(close.iloc[j])
    return None if not np.isfinite(nxt) else (nxt / entry - 1.0) * 100.0


def collect(limit: int, start: str, step: int) -> pd.DataFrame:
    universe = load_top_us_stocks(limit)
    tickers = list(universe["ticker"])
    print(f"Universe: {len(tickers)} tickers vanaf {start}")

    benchmarks = download_benchmarks(start)
    spy = benchmarks.get("SPY", pd.DataFrame()).get("Close")
    sectors = download_sector_benchmarks(start)
    prices = download_ohlcv(tickers, start)
    sector_map = dict(zip(universe["ticker"], universe.get("sector", ["" for _ in tickers])))

    rows = []
    for n, ticker in enumerate(tickers, 1):
        frame = prices.get(ticker)
        if frame is None or len(frame) < 260:
            continue
        etf = SECTOR_ETFS.get(sector_map.get(ticker, ""))
        sector_close = sectors.get(etf, pd.DataFrame()).get("Close") if etf else None
        features = add_indicators(frame, spy)
        features["sector_relative_strength_20d"] = _sector_relative_series(features["Close"], sector_close)
        close = features["Close"]
        # Skip the first year: the 52-week and 200-day fields are not formed yet.
        for i in range(252, len(features) - max(HORIZONS), step):
            row = features.iloc[i]
            technical = new_technical_score(row)
            if not np.isfinite(technical):
                continue
            entry = {
                "date": features.index[i].strftime("%Y-%m-%d"),
                "ticker": ticker,
                "technical": round(float(technical), 2),
            }
            for days in HORIZONS:
                entry[f"return_{days}d"] = _forward(close, i, days)
            rows.append(entry)
        if n % 25 == 0:
            print(f"  {n}/{len(tickers)} verwerkt, {len(rows)} waarnemingen")

    return pd.DataFrame(rows)


def summarise(frame: pd.DataFrame, column: str) -> dict:
    """Forward returns per decile of the score, plus the spread top minus bottom."""
    usable = frame.dropna(subset=[column]).copy()
    if usable.empty:
        return {}
    usable["decile"] = pd.qcut(usable[column].rank(method="first"), DECILES, labels=False) + 1

    out = {"observations": int(len(usable)), "deciles": []}
    for decile, part in usable.groupby("decile"):
        item = {
            "decile": int(decile),
            "score_from": round(float(part[column].min()), 1),
            "score_to": round(float(part[column].max()), 1),
            "n": int(len(part)),
        }
        for days in HORIZONS:
            values = pd.to_numeric(part[f"return_{days}d"], errors="coerce").dropna()
            item[f"avg_{days}d"] = round(float(values.mean()), 3) if len(values) else None
            item[f"win_{days}d"] = round(100.0 * float((values > 0).mean()), 1) if len(values) else None
        out["deciles"].append(item)

    for days in HORIZONS:
        top = out["deciles"][-1].get(f"avg_{days}d")
        bottom = out["deciles"][0].get(f"avg_{days}d")
        if top is not None and bottom is not None:
            out[f"spread_{days}d"] = round(top - bottom, 3)
        baseline = pd.to_numeric(usable[f"return_{days}d"], errors="coerce").dropna()
        out[f"universe_avg_{days}d"] = round(float(baseline.mean()), 3) if len(baseline) else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the price-derived score against forward returns")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--step", type=int, default=5, help="score every Nth trading day")
    parser.add_argument("--output", default="score_validation.json")
    parser.add_argument("--rows", default=None, help="optional CSV of every observation")
    args = parser.parse_args()

    frame = collect(args.limit, args.start, args.step)
    if frame.empty:
        raise SystemExit("Geen waarnemingen verzameld.")

    report = {
        "model_version": MODEL_VERSION,
        "start": args.start,
        "step_days": args.step,
        "note": "Technical only (dislocation x confirmation, 55% of the live score). "
                "The old separate trader-pattern component is gone — the new "
                "methodology folds it into Technical directly. Fundamentals, "
                "Valuation and Analyst direction are excluded here to avoid "
                "look-ahead bias, same as before.",
        "combined": summarise(frame, "technical"),
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.rows:
        frame.to_csv(args.rows, index=False)

    print(f"\nModel {MODEL_VERSION} -- {report['combined']['observations']} waarnemingen\n")
    print("%-8s %14s %8s %9s %9s" % ("deciel", "score", "n", "5d gem.%", "5d win%"))
    for item in report["combined"]["deciles"]:
        print("%-8d %6.1f-%-7.1f %8d %9s %8s%%" % (
            item["decile"], item["score_from"], item["score_to"], item["n"],
            item.get("avg_5d"), item.get("win_5d"),
        ))
    for days in HORIZONS:
        print(f"\nspread hoogste-laagste deciel over {days}d: {report['combined'].get(f'spread_{days}d')}%"
              f"   (universe gemiddeld {report['combined'].get(f'universe_avg_{days}d')}%)")


if __name__ == "__main__":
    main()
