from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from backtest import load_entries
from config import DEFAULT_START
from data import download_benchmarks, download_ohlcv, download_sector_benchmarks, SECTOR_ETFS
from fundamentals import download_fundamentals
from indicators import add_indicators
from model import technical_opportunity_score
from universe import load_top_us_stocks

FEATURES = [
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "rsi_7", "rsi_14", "rsi_21", "macd_histogram", "macd_histogram_change",
    "atr_pct", "bollinger_pct", "bollinger_width", "distance_sma20",
    "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high",
    "distance_6m_high", "distance_52w_high", "distance_support_20d",
    "distance_support_60d", "distance_support_120d", "volume_ratio",
    "volume_ratio_5d", "volatility_20d", "z_score", "close_location",
    "relative_strength_5d", "relative_strength_20d", "sector_relative_strength_20d",
]

EVAL_START = pd.Timestamp("2024-01-01")
THRESHOLDS = [80, 85, 90]
TRADING_HORIZONS = [1, 5, 10, 20, 30]
SCORE_BANDS = [(50, 60), (60, 65), (65, 70), (70, 75), (75, 80), (80, 85), (85, 90), (90, float("inf"))]


def _naive_day_index(index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def vector(row: pd.Series) -> np.ndarray:
    values = pd.to_numeric(row.reindex(FEATURES), errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)


def train_prior(entries: pd.DataFrame, snapshots: dict[pd.Timestamp, dict[str, np.ndarray]], cutoff: pd.Timestamp):
    prior = entries[entries["date"] < cutoff]
    positive_keys = {(str(r.ticker).upper(), pd.Timestamp(r.date).normalize()) for r in prior.itertuples()}
    if len(positive_keys) < 10:
        return None, 0

    positives = []
    by_date: dict[pd.Timestamp, set[str]] = {}
    for ticker, date in positive_keys:
        by_date.setdefault(date, set()).add(ticker)
        v = snapshots.get(date, {}).get(ticker)
        if v is not None:
            positives.append(v)

    rng = np.random.default_rng(42)
    negatives = []
    for date, excluded in by_date.items():
        candidates = [v for t, v in snapshots.get(date, {}).items() if t not in excluded]
        if not candidates:
            continue
        n = min(len(candidates), max(20, len(excluded) * 20))
        idx = rng.choice(len(candidates), size=n, replace=False)
        negatives.extend(candidates[i] for i in idx)

    if len(positives) < 10 or len(negatives) < 10:
        return None, len(positives)

    X = np.asarray(positives + negatives, dtype=float)
    y = np.asarray([1] * len(positives) + [0] * len(negatives), dtype=int)
    pipe = Pipeline([
        ("scale", StandardScaler()),
        ("logreg", LogisticRegression(C=0.35, class_weight="balanced", max_iter=3000, random_state=42)),
    ])
    pipe.fit(X, y)
    return pipe, len(positives)


def probability(pipe: Pipeline, row: pd.Series) -> float:
    return float(pipe.predict_proba(vector(row).reshape(1, -1))[0, 1] * 100.0)


def forward_metrics(close: pd.Series, date: pd.Timestamp) -> dict[str, float | None]:
    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        return {**{f"return_{d}d": None for d in TRADING_HORIZONS}, "return_60d": None, "max_gain_60d": None, "max_drawdown_60d": None}

    index_dates = _naive_day_index(close.index)
    day = pd.Timestamp(date).normalize()
    positions = np.flatnonzero(index_dates == day)
    if len(positions):
        entry_pos = int(positions[-1])
    else:
        prior = np.flatnonzero(index_dates <= day)
        if len(prior) == 0:
            return {**{f"return_{d}d": None for d in TRADING_HORIZONS}, "return_60d": None, "max_gain_60d": None, "max_drawdown_60d": None}
        entry_pos = int(prior[-1])

    entry = float(close.iloc[entry_pos])
    future = close.iloc[entry_pos + 1:]
    out: dict[str, float | None] = {}
    for days in TRADING_HORIZONS:
        out[f"return_{days}d"] = float(future.iloc[days - 1] / entry - 1) if len(future) >= days else None

    # 60D means 60 calendar days. Use the first available trading session on or after that calendar date.
    target_date = day + pd.Timedelta(days=60)
    target_positions = np.flatnonzero(index_dates >= target_date)
    if len(target_positions):
        target_pos = int(target_positions[0])
        out["return_60d"] = float(close.iloc[target_pos] / entry - 1)
        window = close.iloc[entry_pos + 1:target_pos + 1]
        out["max_gain_60d"] = float(window.max() / entry - 1) if len(window) else None
        out["max_drawdown_60d"] = float(window.min() / entry - 1) if len(window) else None
    else:
        out["return_60d"] = None
        out["max_gain_60d"] = None
        out["max_drawdown_60d"] = None
    return out


def _summary_horizon(x: pd.DataFrame, horizon: str) -> dict[str, float | int | None]:
    values = pd.to_numeric(x[f"return_{horizon}"], errors="coerce").dropna()
    return {
        "n": int(len(values)),
        "winrate": float((values > 0).mean()) if len(values) else None,
        "avg_return": float(values.mean()) if len(values) else None,
        "median_return": float(values.median()) if len(values) else None,
    }


def _band_key(lo: int, hi: float) -> str:
    return f"{lo}+" if hi == float("inf") else f"{lo}-{int(hi) - 1}"


def run(output_csv: str = "walk_forward_validation.csv", summary_json: str = "walk_forward_validation.json") -> dict:
    universe = load_top_us_stocks()
    tickers = universe["ticker"].tolist()
    entries = load_entries()
    entries["date"] = pd.to_datetime(entries["date"]).dt.tz_localize(None).dt.normalize()
    entry_dates = set(entries["date"])

    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    spy_close = spy["Close"] if spy is not None and "Close" in spy.columns else None
    prices = download_ohlcv(tickers, DEFAULT_START)
    sector_benchmarks = download_sector_benchmarks(DEFAULT_START)
    # Fundamentals are downloaded for sector classification only. Point-in-time values are not used in historical scoring.
    fundamentals = download_fundamentals(tickers)
    sector_by_ticker = {ticker: data.get("sector") for ticker, data in fundamentals.items()}

    if spy_close is not None and not spy_close.empty:
        market_dates = _naive_day_index(spy_close.index)
    else:
        market_dates = _naive_day_index(sorted({idx for df in prices.values() for idx in df.index}))
    eval_dates = sorted(d for d in market_dates.unique() if d >= EVAL_START)
    if not eval_dates:
        raise RuntimeError("No historical market dates available for walk-forward validation")

    # Build a feature snapshot for EVERY market day, not only trader-entry days.
    # This is critical: the validation must test what the scanner would have seen on normal days too.
    snapshots: dict[pd.Timestamp, dict[str, np.ndarray]] = {}
    feature_rows: dict[pd.Timestamp, dict[str, pd.Series]] = {}
    close_by_ticker: dict[str, pd.Series] = {}

    for ticker, df in prices.items():
        if df.empty or "Close" not in df.columns:
            continue
        features = add_indicators(df, spy_close).copy()
        features.index = _naive_day_index(features.index)
        features = features[~features.index.duplicated(keep="last")]
        close = pd.to_numeric(features["Close"], errors="coerce").dropna()
        close.index = _naive_day_index(close.index)
        close_by_ticker[ticker] = close

        aligned = features.reindex(eval_dates, method="ffill")

        sector = sector_by_ticker.get(ticker)
        sector_etf = SECTOR_ETFS.get(sector)
        sector_close = None
        if sector_etf in sector_benchmarks:
            sector_close = pd.to_numeric(sector_benchmarks[sector_etf]["Close"], errors="coerce").dropna()
            sector_close.index = _naive_day_index(sector_close.index)
        sector_rs_series = None
        if sector_close is not None and not sector_close.empty:
            stock_ret = close.reindex(eval_dates, method="ffill").pct_change(20)
            sector_ret = sector_close.reindex(eval_dates, method="ffill").pct_change(20)
            sector_rs_series = stock_ret - sector_ret

        for date, row in aligned.iterrows():
            date = pd.Timestamp(date).normalize()
            if row.isna().all():
                continue
            row = row.copy()
            row["sector_relative_strength_20d"] = (
                float(sector_rs_series.loc[date])
                if sector_rs_series is not None and date in sector_rs_series.index and pd.notna(sector_rs_series.loc[date])
                else None
            )
            feature_rows.setdefault(date, {})[ticker] = row
            snapshots.setdefault(date, {})[ticker] = vector(row)

    results = []
    model_counts = []
    evaluated_dates = 0
    for date in eval_dates:
        pipe, positives = train_prior(entries, snapshots, pd.Timestamp(date))
        if pipe is None:
            continue
        evaluated_dates += 1
        model_counts.append(positives)
        for ticker, row in feature_rows.get(pd.Timestamp(date), {}).items():
            trader_score = probability(pipe, row)
            technical = float(technical_opportunity_score(row)["technical_opportunity_score"])
            score = 0.70 * trader_score + 0.30 * technical
            metrics = forward_metrics(close_by_ticker[ticker], pd.Timestamp(date))
            results.append({
                "date": pd.Timestamp(date).date().isoformat(),
                "ticker": ticker,
                "score": round(score, 2),
                "trader_score": round(trader_score, 2),
                "technical_score": round(technical, 2),
                "sector_relative_strength_20d": row.get("sector_relative_strength_20d"),
                "training_positive_observations": positives,
                **metrics,
            })

    df = pd.DataFrame(results)
    if df.empty:
        raise RuntimeError("Walk-forward produced no scenarios")
    df.to_csv(output_csv, index=False)

    summary: dict[str, object] = {
        "method": "Daily walk-forward logistic trader-pattern validation across the full curated universe. Each evaluation day trains only on trader entries before that day, then scores every available ticker. Feature snapshots are built for every market day so normal non-entry days are also tested. All scored scenarios are retained for calibration. Fundamentals are excluded from historical scoring because point-in-time fundamentals are unavailable.",
        "evaluation_start": EVAL_START.date().isoformat(),
        "scenarios": int(len(df)),
        "alerts_80_plus": int((df["score"] >= 80).sum()),
        "unique_dates": int(df["date"].nunique()),
        "unique_tickers": int(df["ticker"].nunique()),
        "evaluated_universe_rows": int(len(df)),
        "evaluated_dates": evaluated_dates,
        "market_days_available": len(eval_dates),
        "horizons": {
            "1d": "1 trading day",
            "5d": "5 trading days",
            "10d": "10 trading days",
            "20d": "20 trading days",
            "30d": "30 trading days",
            "60d": "60 calendar days",
        },
        "thresholds": {},
        "score_bands": {},
        "average_positive_training_observations": float(np.mean(model_counts)) if model_counts else None,
    }

    for threshold in THRESHOLDS:
        x = df[df["score"] >= threshold]
        threshold_summary: dict[str, object] = {"alerts": int(len(x))}
        for horizon in ["1d", "5d", "10d", "20d", "30d", "60d"]:
            stats = _summary_horizon(x, horizon)
            threshold_summary[f"n_{horizon}"] = stats["n"]
            threshold_summary[f"winrate_{horizon}"] = stats["winrate"]
            threshold_summary[f"avg_return_{horizon}"] = stats["avg_return"]
            threshold_summary[f"median_return_{horizon}"] = stats["median_return"]
        threshold_summary["avg_max_gain_60d"] = float(x["max_gain_60d"].mean()) if x["max_gain_60d"].notna().any() else None
        threshold_summary["avg_max_drawdown_60d"] = float(x["max_drawdown_60d"].mean()) if x["max_drawdown_60d"].notna().any() else None
        summary["thresholds"][str(threshold)] = threshold_summary

    for lo, hi in SCORE_BANDS:
        x = df[(df["score"] >= lo) & (df["score"] < hi)]
        key = _band_key(lo, hi)
        summary["score_bands"][key] = {"scenarios": int(len(x))}
        for horizon in ["5d", "20d", "30d", "60d"]:
            stats = _summary_horizon(x, horizon)
            summary["score_bands"][key][f"n_{horizon}"] = stats["n"]
            summary["score_bands"][key][f"winrate_{horizon}"] = stats["winrate"]
            summary["score_bands"][key][f"avg_return_{horizon}"] = stats["avg_return"]
            summary["score_bands"][key][f"median_return_{horizon}"] = stats["median_return"]

    Path(summary_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
