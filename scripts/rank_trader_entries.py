"""Where did the trader's buys sit in our ranking, on the day he bought?

This is the scanner's actual objective. Forward-return backtests answer whether
a high score beats a low one on average; they do not answer the question the
scanner was built for, which is whether it surfaces the kind of setup this
trader takes. His calls are a direct answer, and they are the only labelled
examples there are.

The measure is rank, not score: on each buy date the whole universe is scored
and we record where his pick landed. Rank is comparable across days and across
weightings, which a raw score is not. Random placement averages half the
universe, so a median far below that is the signal.

Fundamentals are taken from the current scan rather than from history, because
no point-in-time fundamentals exist. That is look-ahead, so the fundamentals
rows are labelled indicative and should not be used to tune a weight. The
price-derived variants carry no such contamination.

Roughly two dozen examples is enough to notice that a component helps or hurts
badly; it is nowhere near enough to fit weights. Two samples of this size have
already disagreed about fundamentals. Read the shape, not the decimals.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from data import SECTOR_ETFS, download_benchmarks, download_ohlcv, download_sector_benchmarks
from indicators import add_indicators
from main import MODEL_VERSION
from model import new_technical_score
from universe import load_top_us_stocks

TRADES = Path("data/trader_discord_trades.csv")

# What the setup looked like, not just where it ranked. Each is recorded as a
# percentile inside that day's universe: a value is only distinctive if it sits
# somewhere unusual relative to everything else on offer that morning.
PROFILE_FIELDS = [
    "rsi_14", "rsi_7", "z_score", "macd_histogram", "macd_histogram_change",
    "return_1d", "return_3d", "return_5d", "return_7d", "return_10d", "return_14d",
    "return_20d", "return_30d", "distance_sma20", "distance_sma50", "distance_sma200",
    "distance_1m_high", "distance_3m_high", "distance_52w_high",
    "distance_support_20d", "distance_support_60d", "volume_ratio", "volume_ratio_5d",
    "volatility_20d", "atr_pct", "bollinger_pct", "close_location",
    "relative_strength_5d", "relative_strength_20d", "sector_relative_strength_20d",
]
SCAN = Path("public/data/latest_scan.json")
WARMUP_DAYS = 252


def load_buys(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["action"] == "BUY"]
    for row in rows:
        row["date"] = pd.Timestamp(row["date"])
    return rows


def current_fundamentals() -> dict[str, float]:
    if not SCAN.exists():
        return {}
    payload = json.loads(SCAN.read_text(encoding="utf-8"))
    return {
        r["ticker"]: r["fundamental_score"]
        for r in payload.get("results", [])
        if r.get("fundamental_score") is not None
    }


def sector_relative(close: pd.Series, sector_close: pd.Series | None) -> pd.Series:
    """The scanner computes this for the latest bar; history needs it per day."""
    if sector_close is None or len(sector_close) < 21:
        return pd.Series(np.nan, index=close.index)
    aligned = pd.to_numeric(sector_close, errors="coerce").reindex(close.index).ffill()
    return close.pct_change(20) - aligned.pct_change(20)


def build_features(limit: int, start: str) -> dict[str, pd.DataFrame]:
    universe = load_top_us_stocks(limit)
    tickers = list(universe["ticker"])
    sector_of = dict(zip(universe["ticker"], universe.get("sector", ["" for _ in tickers])))
    print(f"Universe: {len(tickers)} tickers vanaf {start}")

    spy = download_benchmarks(start).get("SPY", pd.DataFrame()).get("Close")
    sectors = download_sector_benchmarks(start)
    prices = download_ohlcv(tickers, start)

    features = {}
    for n, ticker in enumerate(tickers, 1):
        frame = prices.get(ticker)
        if frame is None or len(frame) < WARMUP_DAYS:
            continue
        etf = SECTOR_ETFS.get(sector_of.get(ticker, ""))
        sector_close = sectors.get(etf, pd.DataFrame()).get("Close") if etf else None
        enriched = add_indicators(frame, spy)
        enriched["sector_relative_strength_20d"] = sector_relative(enriched["Close"], sector_close)
        features[ticker] = enriched
        if n % 50 == 0:
            print(f"  {n}/{len(tickers)} verwerkt")
    print(f"bruikbare tickers: {len(features)}")
    return features


def score_universe(features: dict[str, pd.DataFrame], day: pd.Timestamp) -> dict[str, dict]:
    """Every ticker's components as the scanner would have seen them that day."""
    out = {}
    for ticker, frame in features.items():
        eligible = frame.loc[frame.index <= day]
        if len(eligible) < WARMUP_DAYS:
            continue
        row = eligible.iloc[-1]
        technical = new_technical_score(row)
        if not np.isfinite(technical):
            continue
        entry = {"technical": float(technical)}
        for field in PROFILE_FIELDS:
            value = row.get(field)
            entry[field] = float(value) if value is not None and np.isfinite(value) else None
        out[ticker] = entry
    return out


def profile_buys(usable, per_day) -> list[dict]:
    """For each buy, where its indicators sat inside that day's universe."""
    rows = []
    for buy in usable:
        scored = per_day.get(buy["date"])
        if not scored or buy["ticker"] not in scored:
            continue
        mine = scored[buy["ticker"]]
        row = {"date": buy["date"].date().isoformat(), "ticker": buy["ticker"]}
        for field in PROFILE_FIELDS:
            value = mine.get(field)
            row[field] = value
            others = [c[field] for c in scored.values() if c.get(field) is not None]
            # A percentile from a handful of peers is noise, but the floor has
            # to be low enough that a small run still produces one.
            if value is None or len(others) < 10:
                row[f"pct_{field}"] = None
            else:
                below = sum(1 for o in others if o < value)
                row[f"pct_{field}"] = round(100.0 * below / len(others), 1)
        rows.append(row)
    return rows


def variants(fundamentals: dict[str, float]) -> dict[str, callable]:
    """The old trader+technical split is gone — the new methodology folds
    trader-pattern similarity into Technical itself (dislocation x
    confirmation). Two variants remain: technical alone, and technical
    blended with current-day fundamentals (labelled indicative, same
    look-ahead caveat as before — no point-in-time fundamentals exist).
    Valuation (10%) and Analyst direction (5%) aren't available per
    historical day here, so this can't reproduce the full live formula."""

    def technical_only(t, c):
        return c["technical"]

    def technical_plus_fundamentals(t, c):
        f = fundamentals.get(t)
        if f is None:
            return None
        # Renormalized Technical 55% / Fundamentals 30% from the live
        # formula (the two components this script can actually compute).
        return (0.55 * c["technical"] + 0.30 * f) / 0.85

    return {
        "alleen technical (nieuwe methode)": technical_only,
        "technical 55% + fundamentals 30%, genormaliseerd (indicatief)": technical_plus_fundamentals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank the trader's buys inside our own scan")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--start", default="2024-06-01")
    parser.add_argument("--trades", default=str(TRADES))
    parser.add_argument("--output", default="public/data/trader_rank.json")
    args = parser.parse_args()

    buys = load_buys(Path(args.trades))
    features = build_features(args.limit, args.start)
    fundamentals = current_fundamentals()

    usable = [b for b in buys if b["ticker"] in features]
    print(f"\nkoopmomenten: {len(buys)}, waarvan {len(usable)} in de universe met genoeg historie")

    # A rank is only meaningful against a reasonably complete field, but the
    # bar has to scale with the universe or a small run ranks nothing at all.
    minimum = max(10, int(0.6 * len(features)))
    per_day, thin = {}, 0
    for day in sorted({b["date"] for b in usable}):
        scored = score_universe(features, day)
        if len(scored) >= minimum:
            per_day[day] = scored
        else:
            thin += 1
    if thin:
        print(f"{thin} koopdag(en) overgeslagen: minder dan {minimum} tickers met genoeg historie")

    report = {"model_version": MODEL_VERSION, "start": args.start,
              "setup_profile": profile_buys(usable, per_day), "variants": {}}
    for label, blend in variants(fundamentals).items():
        placements = []
        for buy in usable:
            scored = per_day.get(buy["date"])
            if not scored or buy["ticker"] not in scored:
                continue
            values = {t: blend(t, c) for t, c in scored.items()}
            values = {t: v for t, v in values.items() if v is not None}
            if buy["ticker"] not in values:
                continue
            order = sorted(values, key=lambda t: -values[t])
            placements.append({
                "date": buy["date"].date().isoformat(),
                "ticker": buy["ticker"],
                "rank": order.index(buy["ticker"]) + 1,
                "of": len(order),
            })
        if not placements:
            continue
        ranks = [p["rank"] for p in placements]
        size = statistics.median(p["of"] for p in placements)
        report["variants"][label] = {
            "n": len(ranks),
            "universe": size,
            "median_rank": statistics.median(ranks),
            "mean_rank": round(statistics.mean(ranks), 1),
            "top_10": sum(1 for r in ranks if r <= 10),
            "top_25": sum(1 for r in ranks if r <= 25),
            "top_50": sum(1 for r in ranks if r <= 50),
            "bottom_half": sum(1 for r in ranks if r > size / 2),
            "placements": sorted(placements, key=lambda p: p["date"]),
        }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nmodel {MODEL_VERSION}\n")
    print("%-40s %4s %8s %7s %7s %7s %12s" % ("weging", "n", "mediaan", "top10", "top25", "top50", "onderste helft"))
    for label, item in report["variants"].items():
        print("%-40s %4d %8.0f %7d %7d %7d %12d" % (
            label, item["n"], item["median_rank"], item["top_10"], item["top_25"], item["top_50"], item["bottom_half"]))
    first = next(iter(report["variants"].values()), None)
    if first:
        print(f"\nwillekeurige plaatsing zou een mediaan van ongeveer {first['universe'] / 2:.0f} geven")

    profile = report["setup_profile"]
    if profile:
        print(f"\nSETUP-PROFIEL over {len(profile)} koopmomenten")
        print("mediane percentielpositie binnen de universe; 50 = doorsnee\n")
        summary = []
        for field in PROFILE_FIELDS:
            values = [r[f"pct_{field}"] for r in profile if r.get(f"pct_{field}") is not None]
            if len(values) >= max(10, len(profile) // 2):
                summary.append((abs(statistics.median(values) - 50), field, statistics.median(values), len(values)))
        for gap, field, median, n in sorted(summary, reverse=True):
            bar = "#" * int(gap / 2)
            print("  %-30s p%-5.0f  n=%-3d %s" % (field, median, n, bar))


if __name__ == "__main__":
    main()
