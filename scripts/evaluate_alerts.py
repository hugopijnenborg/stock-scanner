from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

TABLE = "stock_scanner_alerts"
TRADING_HORIZONS = {1: "1D", 5: "5D", 10: "10D", 20: "20D", 30: "30D"}
TARGETS = [5, 10, 20, 30]


def headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def get_pending(url: str, key: str) -> list[dict]:
    r = requests.get(
        f"{url}/rest/v1/{TABLE}",
        headers=headers(key),
        params={"select": "*", "status": "eq.PENDING", "order": "alert_timestamp.asc", "limit": "1000"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def update_row(url: str, key: str, row_id: str, patch: dict) -> None:
    r = requests.patch(
        f"{url}/rest/v1/{TABLE}",
        headers={**headers(key), "Prefer": "return=minimal"},
        params={"id": f"eq.{row_id}"},
        json=patch,
        timeout=30,
    )
    r.raise_for_status()


def download_history(ticker: str, start: pd.Timestamp) -> pd.DataFrame:
    end = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2)
    hist = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if hist.empty:
        return hist
    if hasattr(hist.columns, "levels") and getattr(hist.columns, "nlevels", 1) > 1:
        hist = hist.xs(ticker, axis=1, level=1) if ticker in hist.columns.get_level_values(1) else hist.xs(ticker, axis=1, level=0)
    return hist.dropna(how="all")


def naive_day(value: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def evaluate(row: dict) -> dict | None:
    timestamp = pd.Timestamp(row.get("entry_timestamp") or row.get("alert_timestamp"))
    entry_day = naive_day(timestamp)
    hist = download_history(row["ticker"], entry_day)
    if hist.empty or "Close" not in hist.columns:
        return None

    close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
    high = pd.to_numeric(hist.get("High", hist["Close"]), errors="coerce").reindex(close.index)
    low = pd.to_numeric(hist.get("Low", hist["Close"]), errors="coerce").reindex(close.index)
    entry = float(row.get("alert_price") or close.iloc[0])
    index_dates = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    forward = close[index_dates > entry_day]
    if forward.empty:
        return None

    patch: dict = {"evaluated_at": datetime.now(timezone.utc).isoformat()}
    for n, label in TRADING_HORIZONS.items():
        if len(forward) >= n:
            value = float(forward.iloc[n - 1])
            field = label.lower()
            patch[f"price_{field}"] = value
            patch[f"return_{field}"] = round((value / entry - 1) * 100, 2)
            patch[f"price_{field}_at"] = pd.Timestamp(forward.index[n - 1]).isoformat()

    target_day = entry_day + pd.Timedelta(days=60)
    target_positions = [i for i, d in enumerate(index_dates) if d >= target_day]
    if target_positions:
        target_pos = target_positions[0]
        value = float(close.iloc[target_pos])
        patch["price_60d"] = value
        patch["return_60d"] = round((value / entry - 1) * 100, 2)
        patch["price_60d_at"] = pd.Timestamp(close.index[target_pos]).isoformat()

    twenty = forward.iloc[: min(20, len(forward))]
    high_20 = high.reindex(twenty.index).dropna()
    low_20 = low.reindex(twenty.index).dropna()
    if not high_20.empty:
        patch["max_gain"] = round((float(high_20.max()) / entry - 1) * 100, 2)
        patch["max_drawdown"] = round((float(low_20.min()) / entry - 1) * 100, 2)
        for target in TARGETS:
            patch[f"hit_{target}pct"] = bool(float(high_20.max()) >= entry * (1 + target / 100))

    sixty_mask = (index_dates > entry_day) & (index_dates <= target_day)
    sixty_window = close[sixty_mask]
    if not sixty_window.empty:
        high_60 = high.reindex(sixty_window.index).dropna()
        low_60 = low.reindex(sixty_window.index).dropna()
        if not high_60.empty:
            patch["max_gain_60d"] = round((float(high_60.max()) / entry - 1) * 100, 2)
        if not low_60.empty:
            patch["max_drawdown_60d"] = round((float(low_60.min()) / entry - 1) * 100, 2)

    patch["status"] = "WIN" if "return_60d" in patch and patch["return_60d"] > 0 else "LOSS" if "return_60d" in patch else "PENDING"
    return patch


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")

    rows = get_pending(url, key)
    updated = 0
    failures = 0
    for row in rows:
        try:
            patch = evaluate(row)
            if patch:
                update_row(url, key, row["id"], patch)
                updated += 1
        except Exception as exc:
            failures += 1
            print(f"Evaluation failed for {row.get('ticker')} {row.get('id')}: {exc}")
    print(f"Evaluated {updated}/{len(rows)} pending scanner alert(s).")
    if failures:
        raise RuntimeError(f"{failures} alert evaluation(s) failed")


if __name__ == "__main__":
    main()
