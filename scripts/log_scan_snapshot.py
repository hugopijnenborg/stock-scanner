"""Record every scanned row of a scan, not just the alerts.

Only logging alerts makes the scanner impossible to evaluate: without the rows
that scored 70 and did not alert, there is nothing to compare the 85s against,
so "do high scores predict anything?" has no answer. This writes the full
universe of each scan, with the raw components and the model version, so a
different weighting can be tested against real history later instead of
waiting weeks for fresh data.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

SCAN_FILE = Path("public/data/latest_scan.json")
TABLE = "stock_scanner_scan_log"
BATCH = 250

# Scanner fields worth keeping for later analysis, mapped to their column.
CARRIED = {
    "company_name": "company_name",
    "price": "price",
    "overall_score": "overall_score",
    "trader_score": "trader_score",
    "technical_score": "technical_score",
    "fundamental_score": "fundamental_score",
    "signal": "signal",
    "rsi_14": "rsi_14",
    "return_5d": "return_5d",
    "return_20d": "return_20d",
    "distance_52w_high": "distance_52w_high",
    "distance_sma50": "distance_sma50",
    "volume_ratio": "volume_ratio",
}


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def build_rows(payload: dict) -> list[dict]:
    """Turn a published scan into one database row per scanned ticker."""
    generated_at = payload.get("generated_at")
    model_version = payload.get("model_version")
    if not generated_at or not model_version:
        raise ValueError("scan is missing generated_at or model_version")

    rows = []
    for result in payload.get("results", []):
        ticker = result.get("ticker")
        if not ticker:
            continue
        row = {
            "scan_generated_at": generated_at,
            "model_version": model_version,
            "ticker": ticker,
        }
        for source, column in CARRIED.items():
            value = result.get(source)
            row[column] = value if column in {"company_name", "signal"} else _number(value)
        rows.append(row)
    return rows


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    if not SCAN_FILE.exists():
        raise FileNotFoundError(SCAN_FILE)

    payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    generated_at = payload.get("generated_at")
    try:
        rows = build_rows(payload)
    except ValueError as error:
        print(f"Nothing logged: {error}.", file=sys.stderr)
        raise SystemExit(1)

    if not rows:
        print("Scan contained no rows; nothing logged.")
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Re-running a scan for the same timestamp must not duplicate rows.
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    written = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start:start + BATCH]
        response = requests.post(
            f"{url}/rest/v1/{TABLE}",
            headers=headers,
            params={"on_conflict": "scan_generated_at,ticker"},
            json=chunk,
            timeout=60,
        )
        response.raise_for_status()
        written += len(chunk)

    print(f"Logged {written} rows for scan {generated_at} (model {rows[0]['model_version']}).")


if __name__ == "__main__":
    main()
