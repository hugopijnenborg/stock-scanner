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
    arr = values.to_numpy(dtype=float)
    return arr if np.isfinite(arr).all() else None


def build_training_data(limit: int = 1000, negatives_per_positive: int = 20):
    universe = load_top_us_stocks(limit)
    tickers = universe["ticker"].dropna().astype(str).str.upper().tolist()
    entries = load_entries()
    entries["date"] = pd.to_datetime(entries["date"]).dt.tz_localize(None).dt.normalize()
    entry_dates = sorted(entries["date"].unique())
    positive_keys = {(str(t).upper(), d) for t, d in zip(entries["ticker"], entries["date"])}
    positive_by_date = {}
    for ticker, date in positive_keys:
        positive_by_date.setdefault(date, set()).add(ticker)

    benchmarks = download_benchmarks(DEFAULT_START)
    spy = benchmarks.get("SPY")
    spy_close = spy["Close"] if spy is not None and "Close" in spy.columns else None
    prices = download_ohlcv(tickers, DEFAULT_START)

    prior_dates = set()
    for ticker, entry_date in positive_keys:
        df = prices.get(ticker)
        if df is None or df.empty:
            continue
        idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
        prior = idx[idx < entry_date]
        if len(prior):
            prior_dates.add(prior[-1])
            positive_by_date.setdefault(prior[-1], set()).add(ticker)

    dates = sorted(set(entry_dates) | prior_dates)
    snapshots: dict[pd.Timestamp, dict[str, np.ndarray]] = {d: {} for d in dates}
    positive_vectors = []
    rng = np.random.default_rng(42)

    for ticker, df in prices.items():
        if df.empty or "Close" not in df.columns:
            continue
        features = add_indicators(df, spy_close)
        ticker = ticker.upper()
        for date in dates:
            eligible = features.loc[features.index.normalize() <= date]
            if eligible.empty:
                continue
            vector = _clean_row(eligible.iloc[-1])
            if vector is None:
                continue
            snapshots[date][ticker] = vector
            if (ticker, date) in positive_keys or ticker in positive_by_date.get(date, set()):
                positive_vectors.append(vector)

    positive_vectors = list({vector.tobytes(): vector for vector in positive_vectors}.values())

    negative_vectors = []
    for date in dates:
        excluded = positive_by_date.get(date, set())
        candidates = [v for t, v in snapshots[date].items() if t not in excluded]
        if not candidates:
            continue
        n = min(len(candidates), max(negatives_per_positive, len(excluded) * negatives_per_positive))
        idx = rng.choice(len(candidates), size=n, replace=False)
        negative_vectors.extend(candidates[i] for i in idx)

    X = np.asarray(positive_vectors + negative_vectors, dtype=float)
    y = np.asarray([1] * len(positive_vectors) + [0] * len(negative_vectors), dtype=int)
    return X, y, len(positive_vectors)


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
    importance = pd.Series(clf.coef_[0], index=FEATURES).sort_values(key=np.abs, ascending=False)

    payload = {
        "version": 2,
        "features": FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "positive_observations": int(positive_count),
        "training_observations": int(len(y)),
        "negative_observations": int((y == 0).sum()),
        "top_feature_importance": [{"feature": k, "standardized_coefficient": float(v)} for k, v in importance.head(15).items()],
        "method": "balanced logistic regression on trader entries plus one trading day pre-entry vs sampled same-date non-entries",
        "warning": "Research prototype. It uses the current top-1000 universe for historical controls and is not a guarantee of future returns.",
    }
    Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
