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
from data import download_benchmarks, download_ohlcv
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
    "relative_strength_5d", "relative_strength_20d", "market_regime_score",
]
EVAL_START = pd.Timestamp("2025-01-01")
THRESHOLDS = [80, 85, 90]


def vector(row: pd.Series) -> np.ndarray:
    values = pd.to_numeric(row.reindex(FEATURES), errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)


def train_prior(entries, snapshots, cutoff):
    prior = entries[entries["date"] < cutoff]
    positive_keys = {(str(r.ticker).upper(), pd.Timestamp(r.date).normalize()) for r in prior.itertuples()}
    if len(positive_keys) < 10:
        return None, 0
    positives = []
    by_date = {}
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
        negatives.extend(candidates[i] for i in rng.choice(len(candidates), size=n, replace=False))
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


def probability(pipe, row):
    return float(pipe.predict_proba(vector(row).reshape(1, -1))[0, 1] * 100.0)


def forward_metrics(close, date):
    series = pd.to_numeric(close, errors="coerce").dropna().sort_index()
    entry_rows = series[series.index.normalize() == date.normalize()]
    if entry_rows.empty:
        return {"return_1d": None, "return_5d": None, "return_10d": None, "return_20d": None, "max_gain_20d": None, "max_drawdown_20d": None}
    entry = float(entry_rows.iloc[-1])
    future = series[series.index.normalize() > date.normalize()]
    out = {}
    for days in [1, 5, 10, 20]:
        out[f"return_{days}d"] = float(future.iloc[days - 1] / entry - 1) if len(future) >= days else None
    window = future.iloc[:20]
    out["max_gain_20d"] = float(window.max() / entry - 1) if len(window) else None
    out["max_drawdown_20d"] = float(window.min() / entry - 1) if len(window) else None
    return out


def _metric(x, column, fn):
    values = pd.to_numeric(x[column], errors="coerce").dropna()
    return float(fn(values)) if len(values) else None


def _summary_metrics(x):
    return {
        "alerts": int(len(x)),
        "winrate_1d": _metric(x, "return_1d", lambda v: (v > 0).mean()),
        "winrate_5d": _metric(x, "return_5d", lambda v: (v > 0).mean()),
        "winrate_10d": _metric(x, "return_10d", lambda v: (v > 0).mean()),
        "winrate_20d": _metric(x, "return_20d", lambda v: (v > 0).mean()),
        "avg_return_5d": _metric(x, "return_5d", np.mean),
        "avg_return_20d": _metric(x, "return_20d", np.mean),
        "median_return_20d": _metric(x, "return_20d", np.median),
        "avg_max_gain_20d": _metric(x, "max_gain_20d", np.mean),
        "avg_max_drawdown_20d": _metric(x, "max_drawdown_20d", np.mean),
    }


def run(output_csv="walk_forward_validation.csv", summary_json="walk_forward_validation.json"):
    universe = load_top_us_stocks()
    tickers = universe["ticker"].tolist()
    entries = load_entries()
    entries["date"] = pd.to_datetime(entries["date"]).dt.tz_localize(None).dt.normalize()
    eval_dates = sorted(d for d in entries["date"].unique() if d >= EVAL_START)
    if not eval_dates:
        raise RuntimeError("No trader entries available for walk-forward validation")

    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    spy_close = spy["Close"] if spy is not None and "Close" in spy.columns else None
    prices = download_ohlcv(tickers, DEFAULT_START)
    snapshots = {}
    feature_rows = {}
    close_by_ticker = {}
    all_dates = set(eval_dates) | set(entries["date"])

    for ticker, df in prices.items():
        if df.empty or "Close" not in df.columns:
            continue
        features = add_indicators(df, spy_close)
        close_by_ticker[ticker] = pd.to_numeric(features["Close"], errors="coerce")
        for date in sorted(all_dates):
            eligible = features.loc[features.index.normalize() <= date]
            if eligible.empty:
                continue
            row = eligible.iloc[-1]
            snapshots.setdefault(date, {})[ticker] = vector(row)
            feature_rows.setdefault(date, {})[ticker] = row

    results = []
    model_counts = []
    all_technical_scores = []
    evaluated_rows = 0
    for date in eval_dates:
        pipe, positives = train_prior(entries, snapshots, pd.Timestamp(date))
        if pipe is None:
            continue
        model_counts.append(positives)
        for ticker, row in feature_rows.get(pd.Timestamp(date), {}).items():
            technical = float(technical_opportunity_score(row)["technical_opportunity_score"])
            all_technical_scores.append(technical)
            evaluated_rows += 1
            trader_score = probability(pipe, row)
            score = 0.70 * trader_score + 0.30 * technical
            if score < 80:
                continue
            results.append({
                "date": pd.Timestamp(date).date().isoformat(),
                "ticker": ticker,
                "score": round(score, 2),
                "trader_score": round(trader_score, 2),
                "technical_score": round(technical, 2),
                "market_regime_score": round(float(row.get("market_regime_score", 0.5)) * 100, 2),
                **forward_metrics(close_by_ticker[ticker], pd.Timestamp(date)),
            })

    df = pd.DataFrame(results)
    if df.empty:
        raise RuntimeError("Walk-forward produced no 80+ observations")
    df.to_csv(output_csv, index=False)
    tech = pd.Series(all_technical_scores, dtype=float)
    summary = {
        "method": "Walk-forward logistic trader-pattern model. Each evaluation date trains only on earlier trader entries. Fundamentals are excluded because point-in-time historical fundamentals are unavailable.",
        "evaluation_start": EVAL_START.date().isoformat(),
        "observations": int(len(df)),
        "unique_dates": int(df["date"].nunique()),
        "unique_tickers": int(df["ticker"].nunique()),
        "evaluated_universe_rows": evaluated_rows,
        "technical_score_distribution": {
            "count": int(len(tech)),
            "mean": float(tech.mean()) if len(tech) else None,
            "median": float(tech.median()) if len(tech) else None,
            "p10": float(tech.quantile(0.10)) if len(tech) else None,
            "p25": float(tech.quantile(0.25)) if len(tech) else None,
            "p75": float(tech.quantile(0.75)) if len(tech) else None,
            "p90": float(tech.quantile(0.90)) if len(tech) else None,
            "share_70_plus": float((tech >= 70).mean()) if len(tech) else None,
            "share_80_plus": float((tech >= 80).mean()) if len(tech) else None,
        },
        "thresholds": {},
        "average_positive_training_observations": float(np.mean(model_counts)) if model_counts else None,
    }
    for threshold in THRESHOLDS:
        summary["thresholds"][str(threshold)] = _summary_metrics(df[df["score"] >= threshold])
    Path(summary_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
