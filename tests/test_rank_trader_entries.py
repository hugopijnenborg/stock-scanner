"""The rank tool is the scanner's objective, so it has to actually run.

The score validator shipped with an import error and burned a live run before
anyone learned anything. This drives the whole tool on synthetic prices: parse,
feature build, per-day scoring, ranking, JSON output.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
TICKERS = [f"T{i:03d}" for i in range(14)]
BUY_DATES = ["2026-05-07", "2026-06-18", "2026-07-29"]


def _prices(seed: int, n: int = 700) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * (1 + abs(rng.normal(0, 0.01, n))),
            "Low": close * (1 - abs(rng.normal(0, 0.01, n))),
            "Close": close,
            "Volume": rng.integers(1_000_000, 9_000_000, n).astype(float),
        },
        index=pd.bdate_range("2024-01-01", periods=n),
    )


@pytest.fixture(scope="module")
def tool(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("rank_trader", REPO / "scripts" / "rank_trader_entries.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.download_ohlcv = lambda tickers, start=None, end=None: {t: _prices(i) for i, t in enumerate(tickers)}
    module.download_benchmarks = lambda start=None, end=None: {"SPY": _prices(99)}
    module.download_sector_benchmarks = lambda start=None, end=None: {"XLK": _prices(98)}
    module.load_top_us_stocks = lambda limit=None: pd.DataFrame({"ticker": TICKERS, "sector": ["Technology"] * len(TICKERS)})
    module.SECTOR_ETFS = {"Technology": "XLK"}
    return module


@pytest.fixture(scope="module")
def trades(tmp_path_factory):
    path = tmp_path_factory.mktemp("trades") / "trades.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "time", "action", "ticker", "price", "quote"])
        writer.writeheader()
        for i, date in enumerate(BUY_DATES):
            writer.writerow({"date": date, "time": "16:00", "action": "BUY", "ticker": TICKERS[i], "price": 10, "quote": ""})
        writer.writerow({"date": "2026-05-07", "time": "16:00", "action": "SELL", "ticker": TICKERS[5], "price": 12, "quote": ""})
    return path


def test_it_imports_its_project_modules(tool):
    for name in ("technical_opportunity_score", "trader_setup_score", "add_indicators", "MODEL_VERSION"):
        assert hasattr(tool, name)


def test_only_buys_are_measured(tool, trades):
    buys = tool.load_buys(trades)
    assert len(buys) == len(BUY_DATES)
    assert all(isinstance(b["date"], pd.Timestamp) for b in buys)


def test_scoring_a_day_covers_the_universe(tool):
    features = tool.build_features(len(TICKERS), "2024-01-01")
    scored = tool.score_universe(features, pd.Timestamp("2026-07-29"))
    assert len(scored) == len(TICKERS)
    for components in scored.values():
        assert np.isfinite(components["technical"]) and np.isfinite(components["trader"])


def test_a_day_without_enough_history_is_skipped(tool):
    """Scoring before the 52-week fields exist would read a high built from weeks."""
    features = tool.build_features(len(TICKERS), "2024-01-01")
    assert tool.score_universe(features, pd.Timestamp("2024-03-01")) == {}


def test_the_full_run_produces_ranked_placements(tool, trades, tmp_path, monkeypatch):
    out = tmp_path / "rank.json"
    monkeypatch.setattr("sys.argv", ["rank_trader_entries.py", "--limit", str(len(TICKERS)),
                                     "--start", "2024-01-01", "--trades", str(trades), "--output", str(out)])
    tool.main()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["model_version"]
    variant = report["variants"]["trader + technical"]
    assert variant["n"] == len(BUY_DATES)
    for placement in variant["placements"]:
        assert 1 <= placement["rank"] <= placement["of"]
        assert placement["of"] == len(TICKERS)


def test_every_variant_is_reported(tool, trades, tmp_path, monkeypatch):
    out = tmp_path / "rank2.json"
    monkeypatch.setattr("sys.argv", ["rank_trader_entries.py", "--limit", str(len(TICKERS)),
                                     "--start", "2024-01-01", "--trades", str(trades), "--output", str(out)])
    tool.main()
    variants = json.loads(out.read_text(encoding="utf-8"))["variants"]
    assert {"trader + technical", "alleen technical", "alleen trader"} <= set(variants)


def test_the_setup_profile_places_each_buy_inside_its_own_day(tool, trades, tmp_path, monkeypatch):
    """A raw RSI of 30 means nothing; being the lowest RSI on offer that day does.

    The profile is what the reverse engineering reads, so every recorded value
    has to be a percentile inside that day's universe, not an absolute number.
    """
    out = tmp_path / "rank3.json"
    monkeypatch.setattr("sys.argv", ["rank_trader_entries.py", "--limit", str(len(TICKERS)),
                                     "--start", "2024-01-01", "--trades", str(trades), "--output", str(out)])
    tool.main()
    profile = json.loads(out.read_text(encoding="utf-8"))["setup_profile"]
    assert len(profile) == len(BUY_DATES)
    for row in profile:
        assert row["ticker"] in TICKERS
        percentiles = [v for k, v in row.items() if k.startswith("pct_") and v is not None]
        assert percentiles, f"{row['ticker']} heeft geen percentielen"
        assert all(0 <= v <= 100 for v in percentiles)


def test_the_profile_keeps_the_raw_value_next_to_its_percentile():
    """Both are needed: the percentile says it is unusual, the value says how much."""
    spec = importlib.util.spec_from_file_location("rank_trader2", REPO / "scripts" / "rank_trader_entries.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "rsi_14" in module.PROFILE_FIELDS
    assert "distance_52w_high" in module.PROFILE_FIELDS
    assert "volume_ratio" in module.PROFILE_FIELDS
