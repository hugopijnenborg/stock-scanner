from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from config import DEFAULT_START
from data import download_benchmarks, download_ohlcv
from indicators import add_indicators
from universe import load_top_us_stocks

FEATURES = [
    "rsi_7", "rsi_14", "rsi_21", "macd", "macd_signal", "macd_histogram",
    "macd_histogram_change", "atr_pct", "bollinger_pct", "bollinger_width",
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "distance_sma20", "distance_sma50", "distance_sma200", "distance_1m_high",
    "distance_3m_high", "distance_6m_high", "distance_52w_high",
    "distance_support_20d", "distance_support_60d", "distance_support_120d",
    "volume_ratio", "volume_ratio_5d", "volatility_20d", "z_score", "close_location",
    "relative_strength_5d", "relative_strength_20d",
]

OUT = Path("learned_model.json")
HISTORY = Path("data/trader_history.csv")


def _snapshot(prices: pd.DataFrame, benchmark: pd.Series | None, date: pd.Timestamp) -> pd.Series | None:
    if prices.empty:
        return None
    prices = prices.loc[prices.index <= date]
    if len(prices) < 210:
        return None
    ind = add_indicators(prices, benchmark)
    row = ind.iloc[-1]
    values = pd.to_numeric(row.reindex(FEATURES), errors="coerce")
    if values.isna().mean() > 0.30:
        return None
    return values.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def main() -> None:
    trades = pd.read_csv(HISTORY)
    trades["date"] = pd.to_datetime(trades["date"])
    trades = trades.drop_duplicates(subset=["date", "ticker", "price"]).sort_values("date")
    universe = load_top_us_stocks(1000)
    tickers = universe["ticker"].tolist()
    start = min(pd.Timestamp(DEFAULT_START), trades["date"].min() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    benchmarks = download_benchmarks(start)
    spy = benchmarks.get("SPY")
    benchmark_close = spy["Close"] if spy is not None and "Close" in spy else None
    prices = download_ohlcv(tickers, start)

    positive = []
    for _, trade in trades.iterrows():
        ticker = str(trade["ticker"]).upper()
        if ticker not in prices:
            continue
        snap = _snapshot(prices[ticker], benchmark_close, trade["date"])
        if snap is not None:
            positive.append((trade["date"], ticker, snap, 1))

    # Same-date controls: sample up to 8 non-traded universe names for each
    # positive. This controls for market regime and prevents the model from
    # learning that a particular calendar period was simply bullish/bearish.
    rng = np.random.default_rng(42)
    positive_keys = {(d.date(), t) for d, t, _, _ in positive}
    negative = []
    by_date = {}
    for d, t, snap, y in positive:
        by_date.setdefault(d.date(), set()).add(t)
    for date, chosen in by_date.items():
        candidates = [t for t in prices if t not in chosen]
        if not candidates:
            continue
        rng.shuffle(candidates)
        count = min(8 * len(chosen), len(candidates))
        target_date = pd.Timestamp(date)
        for ticker in candidates[:count]:
            snap = _snapshot(prices[ticker], benchmark_close, target_date)
            if snap is not None:
                negative.append((target_date, ticker, snap, 0))

    samples = positive + negative
    if len(positive) < 15 or len(negative) < 30:
        raise RuntimeError(f"Not enough training data: {len(positive)} positive, {len(negative)} negative")

    df = pd.DataFrame([s[2].to_dict() for s in samples])
    X = df[FEATURES].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    y = np.array([s[3] for s in samples], dtype=int)
    dates = np.array([s[0].value for s in samples])

    order = np.argsort(dates)
    X, y = X[order], y[order]
    split = max(int(len(y) * 0.70), 1)
    split = min(split, len(y) - 1)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X[:split])
    X_test = scaler.transform(X[split:])
    clf = LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5, random_state=42)
    clf.fit(X_train, y[:split])

    test_auc = None
    if len(np.unique(y[split:])) == 2:
        test_auc = float(roc_auc_score(y[split:], clf.predict_proba(X_test)[:, 1]))

    # Refit on all available historical examples after the out-of-sample check.
    scaler_all = StandardScaler()
    X_all = scaler_all.fit_transform(X)
    clf_all = LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5, random_state=42)
    clf_all.fit(X_all, y)

    payload = {
        "version": 2,
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "positive_samples": len(positive),
        "negative_samples": len(negative),
        "test_auc": test_auc,
        "features": FEATURES,
        "mean": scaler_all.mean_.tolist(),
        "scale": scaler_all.scale_.tolist(),
        "coef": clf_all.coef_[0].tolist(),
        "intercept": float(clf_all.intercept_[0]),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ["version", "positive_samples", "negative_samples", "test_auc"]}, indent=2))


if __name__ == "__main__":
    main()
