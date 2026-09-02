from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

SCAN_FILE = Path("public/data/latest_scan.json")
TABLE = "stock_scanner_alerts"
ACTIVE_DAYS = 60


def _headers(key: str, prefer: str | None = None) -> dict[str, str]:
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    if not SCAN_FILE.exists():
        raise FileNotFoundError(SCAN_FILE)

    payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    generated_at = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    active_since = (generated - timedelta(days=ACTIVE_DAYS)).isoformat()

    # One active scanner alert per ticker. Repeated scans update peak_score,
    # while the original entry timestamp/price/score remain unchanged.
    response = requests.get(
        f"{url}/rest/v1/{TABLE}",
        headers=_headers(key),
        params={
            "select": "id,ticker,alert_timestamp,status,peak_score,peak_score_at",
            "alert_timestamp": f"gte.{active_since}",
            "order": "alert_timestamp.desc",
            "limit": "1000",
        },
        timeout=30,
    )
    response.raise_for_status()
    existing = response.json()
    active_by_ticker = {}
    for item in existing:
        ticker = item.get("ticker")
        if not ticker or ticker in active_by_ticker:
            continue
        if item.get("status") == "PENDING":
            active_by_ticker[ticker] = item

    created = 0
    updated = 0
    alerts = []
    for row in payload.get("results", []):
        ticker = row.get("ticker")
        if row.get("signal") != "ALERT" or not ticker:
            continue
        current_score = row.get("overall_score")
        if ticker in active_by_ticker:
            existing_row = active_by_ticker[ticker]
            old_peak = existing_row.get("peak_score")
            try:
                old_peak = float(old_peak) if old_peak is not None else None
                current = float(current_score) if current_score is not None else None
            except (TypeError, ValueError):
                old_peak, current = None, None
            if current is not None and (old_peak is None or current > old_peak):
                patch = {"peak_score": current, "peak_score_at": generated_at}
                r = requests.patch(
                    f"{url}/rest/v1/{TABLE}",
                    headers={**_headers(key), "Prefer": "return=minimal"},
                    params={"id": f"eq.{existing_row['id']}"},
                    json=patch,
                    timeout=30,
                )
                r.raise_for_status()
                updated += 1
            continue

        alerts.append({
            "ticker": ticker,
            "company_name": row.get("company_name"),
            "alert_timestamp": generated_at,
            "entry_timestamp": generated_at,
            "alert_price": row.get("price"),
            "score": current_score,
            "initial_score": current_score,
            "peak_score": current_score,
            "peak_score_at": generated_at,
            "trader_score": row.get("trader_similarity_score"),
            "technical_score": row.get("technical_score"),
            "fundamental_score": row.get("fundamental_score"),
            "status": "PENDING",
        })

    if alerts:
        response = requests.post(
            f"{url}/rest/v1/{TABLE}",
            headers=_headers(key, "resolution=ignore-duplicates,return=minimal"),
            json=alerts,
            timeout=30,
        )
        response.raise_for_status()
        created = len(alerts)

    print(f"Created {created} new scanner alert(s), updated {updated} peak score(s).")


if __name__ == "__main__":
    main()
