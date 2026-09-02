from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf

TABLE = "stock_scanner_alerts"
# Trading-day horizons. 40 trading days is used as the scanner's approximately 2-month horizon.
HORIZONS = {1: "1D", 5: "5D", 10: "10D", 20: "20D", 30: "30D", 40: "40D"}
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


def evaluate(row: dict) -> dict | None:
    timestamp = pd.Timestamp(row.get("entry_timestamp") or row.get("alert_timestamp"))
    hist = download_history(row["ticker"], timestamp.normalize())
    if hist.empty or "Close" not in hist.columns:
        return None

    close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
    high = pd.to_numeric(hist.get("High", hist["Close"]), errors="coerce").reindex(close.index)
    low = pd.to_numeric(hist.get("Low", hist["Close"]), errors="coerce").reindex(close.index)
    entry = float(row.get("alert_price") or close.iloc[0])
    entry_date = timestamp.date()
    forward = close[close.index.date > entry_date]
    if forward.empty:
        return None

    patch: dict = {"evaluated_at": datetime.now(timezone.utc).isoformat()}
    for n, label in HORIZONS.items():
        if len(forward) >= n:
            value = float(forward.iloc[n - 1])
            field = label.split("D")[0].lower()
            patch[f"price_{field}d"] = value
            patch[f"return_{field}d"] = round((value / entry - 1) * 100, 2)
            patch[f"price_{field}d_at"] = pd.Timestamp(forward.index[n - 1]).isoformat()

    # Keep the existing 20D excursion metrics for compatibility and extend them to 40D.
    for window_days in (20, 40):
        available = forward.iloc[: min(window_days, len(forward))]
        high_forward = high.reindex(available.index).dropna()
        low_forward = low.reindex(available.index).dropna()
        if not high_forward.empty and window_days == 20:
            patch["max_gain"] = round((float(high_forward.max()) / entry - 1) * 100, 2)
            patch["max_drawdown"] = round((float(low_forward.min()) / entry - 1) * 100, 2)
            for target in TARGETS:
                patch[f"hit_{target}pct"] = bool(float(high_forward.max()) >= entry * (1 + target / 100))
        if not high_forward.empty and window_days == 40:
            patch["max_gain_40d"] = round((float(high_forward.max()) / entry - 1) * 100, 2)
            patch["max_drawdown_40d"] = round((float(low_forward.min()) / entry - 1) * 100, 2)

    # A trade remains pending until the full approximately 2-month horizon is available.
    patch["status"] = "WIN" if "return_40d" in patch and patch["return_40d"] > 0 else "LOSS" if "return_40d" in patch else "PENDING"
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
