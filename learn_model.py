from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import DEFAULT_START
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from universe import load_top_us_stocks
from backtest import load_entries

FEATURES = [
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "rsi_7", "rsi_14", "rsi_21", "macd_histogram", "macd_histogram_change",
    "atr_pct", "bollinger_pct", "bollinger_width", "distance_sma20",
    "distance_sma50", "distance_sma200", "distance_1m_high", "distance_3m_high",
    "distance_6m_high", "distance_52w_high", "distance_support_20d",
    "distance_support_60d", "distance_support_120d", "volume_ratio",
    "volume_ratio_5d", "volatility_20d", "z_score", "close_location",
    "relative_strength_5d", "relative_strength_20d",
]


def _clean_row(row: pd.Series) -> np.ndarray | None:
    values = pd.to_numeric(row.reindex(FEATURES), errors="coerce")
    values = values.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        return None
    return values.to_numpy(dtype=float)


def build_training_data(limit: int = 1000, negatives_per_positive: int = 20):
    universe = load_top_us_stocks(limit)
    universe_tickers = universe["ticker"].dropna().astype(str).str.upper().tolist()
    entries = load_entries()
    entry_dates = pd.to_datetime(entries["date"]).dt.tz_localize(None).dt.normalize()
    positive_keys = {(str(t).upper(), d) for t, d in zip(entries["ticker"], entry_dates)}

    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    spy_close = spy["Close"] if spy is not None and "Close" in spy.columns else None
    prices = download_ohlcv(universe_tickers, DEFAULT_START)

    rng = np.random.default_rng(42)
    X, y = [], []
    positive_count = 0

    for ticker, df in prices.items():
        if df.empty or "Close" not in df.columns:
            continue
        features = add_indicators(df, spy_close)
        for date in sorted(set(entry_dates)):
            eligible = features.loc[features.index.normalize() <= date]
            if eligible.empty:
                continue
            row = eligible.iloc[-1]
            key = (ticker.upper(), date)
            vector = _clean_row(row)
            if vector is None:
                continue
            if key in positive_keys:
                X.append(vector)
                y.append(1)
                positive_count += 1

    positives = [(x, d) for x, d in zip(X, entry_dates)] if False else None

    # Rebuild negatives by date. Sampling is deterministic and avoids flooding
    # the classifier with near-identical observations.
    positive_tickers_by_date = {}
    for ticker, date in zip(entries["ticker"].astype(str).str.upper(), entry_dates):
        positive_tickers_by_date.setdefault(date, set()).add(ticker)

    for date in sorted(set(entry_dates)):
        candidates = []
        for ticker, df in prices.items():
            if ticker.upper() in positive_tickers_by_date.get(date, set()):
                continue
            features = add_indicators(df, spy_close)
            eligible = features.loc[features.index.normalize() <= date]
            if eligible.empty:
                continue
            vector = _clean_row(eligible.iloc[-1])
            if vector is not None:
                candidates.append(vector)
        if candidates:
            n = min(len(candidates), max(negatives_per_positive, len(positive_tickers_by_date.get(date, set())) * negatives_per_positive))
            for vector in candidates[rng.choice(len(candidates), size=n, replace=False)]:
                X.append(vector)
                y.append(0)

    return np.asarray(X), np.asarray(y), positive_count


def train(limit: int = 1000, negatives_per_positive: int = 20, output: str = "learned_model.json") -> dict:
    X, y, positive_count = build_training_data(limit, negatives_per_positive)
    if positive_count < 10 or len(np.unique(y)) < 2:
        raise RuntimeError("Not enough positive/negative observations to train the model")

    model = Pipeline([
        ("scale", StandardScaler()),
        ("logreg", LogisticRegression(C=0.35, class_weight="balanced", max_iter=3000, random_state=42)),
    ])
    model.fit(X, y)

    scaler = model.named_steps["scale"]
    clf = model.named_steps["logreg"]
    coef = clf.coef_[0] / scaler.scale_
    intercept = float(clf.intercept_[0] - np.dot(clf.coef_[0], scaler.mean_ / scaler.scale_))
    importance = pd.Series(coef, index=FEATURES).sort_values(key=np.abs, ascending=False)

    payload = {
        "version": 1,
        "features": FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "positive_observations": int(positive_count),
        "training_observations": int(len(y)),
        "top_feature_importance": [{"feature": k, "coefficient": float(v)} for k, v in importance.head(15).items()],
        "method": "balanced logistic regression on trader entries vs sampled same-date non-entries",
    }
    Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
