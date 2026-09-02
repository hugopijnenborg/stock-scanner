from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

SCAN_FILE = Path("public/data/latest_scan.json")
TABLE = "stock_scanner_alerts"


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
    scan_date = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date().isoformat()

    # One own alert per ticker per trading day. This prevents repeated 30-minute
    # scans from artificially inflating the performance statistics.
    response = requests.get(
        f"{url}/rest/v1/{TABLE}",
        headers=_headers(key),
        params={"select": "ticker,alert_timestamp", "alert_timestamp": f"gte.{scan_date}T00:00:00Z", "limit": "1000"},
        timeout=30,
    )
    response.raise_for_status()
    existing = response.json()
    existing_tickers = {x.get("ticker") for x in existing}

    alerts = []
    for row in payload.get("results", []):
        if row.get("signal") != "ALERT" or not row.get("ticker") or row.get("ticker") in existing_tickers:
            continue
        alerts.append({
            "ticker": row.get("ticker"),
            "company_name": row.get("company_name"),
            "alert_timestamp": generated_at,
            "entry_timestamp": generated_at,
            "alert_price": row.get("price"),
            "score": row.get("overall_score"),
            "trader_score": row.get("trader_similarity_score"),
            "technical_score": row.get("technical_score"),
            "fundamental_score": row.get("fundamental_score"),
            "status": "PENDING",
        })
    if not alerts:
        print("No new own alerts to save.")
        return

    response = requests.post(
        f"{url}/rest/v1/{TABLE}",
        headers=_headers(key, "resolution=ignore-duplicates,return=minimal"),
        json=alerts,
        timeout=30,
    )
    response.raise_for_status()
    print(f"Saved {len(alerts)} new scanner alert(s) to Supabase.")


if __name__ == "__main__":
    main()
