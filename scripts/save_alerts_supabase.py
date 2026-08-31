from __future__ import annotations

import json
import os
from pathlib import Path

import requests

SCAN_FILE = Path("public/data/latest_scan.json")
TABLE = "stock_scanner_alerts"


def main() -> None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("Supabase credentials not configured. Skipping alert persistence.")
        return
    if not SCAN_FILE.exists():
        raise FileNotFoundError(SCAN_FILE)

    payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
    alerts = []
    for row in payload.get("results", []):
        if row.get("signal") != "ALERT":
            continue
        alerts.append({
            "ticker": row.get("ticker"),
            "company_name": row.get("company_name"),
            "alert_timestamp": payload.get("generated_at"),
            "alert_price": row.get("price"),
            "score": row.get("overall_score"),
            "trader_score": row.get("trader_similarity_score"),
            "technical_score": row.get("technical_score"),
            "fundamental_score": row.get("fundamental_score"),
            "status": "PENDING",
        })
    if not alerts:
        print("No 80+ alerts to save.")
        return

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=minimal",
    }
    response = requests.post(f"{url}/rest/v1/{TABLE}", headers=headers, json=alerts, timeout=30)
    response.raise_for_status()
    print(f"Saved {len(alerts)} scanner alert(s) to Supabase.")


if __name__ == "__main__":
    main()
