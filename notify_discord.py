from __future__ import annotations

import os
from typing import Any

import requests


def send_alerts(results: list[dict[str, Any]], webhook_url: str | None = None, threshold: float = 85.0) -> int:
    webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not configured; skipping Discord alerts")
        return 0

    alerts = [r for r in results if float(r.get("overall_score", 0)) >= threshold]
    alerts = sorted(alerts, key=lambda r: float(r.get("overall_score", 0)), reverse=True)[:10]
    sent = 0
    for row in alerts:
        score = float(row.get("overall_score", 0))
        similarity = float(row.get("trader_similarity_score", 0))
        setup = str(row.get("setup_type", "unknown")).title()
        price = float(row.get("price", 0))
        fields = [
            {"name": "Setup", "value": setup, "inline": True},
            {"name": "Trader similarity", "value": f"{similarity:.0f}/100", "inline": True},
            {"name": "5D move", "value": f"{float(row.get('return_5d', 0))*100:.1f}%", "inline": True},
            {"name": "RSI 14", "value": f"{float(row.get('rsi_14', 0)):.1f}", "inline": True},
            {"name": "Reversal", "value": f"{float(row.get('reversal_trigger', 0)):.0f}/100", "inline": True},
        ]
        payload = {
            "username": "Trader Scanner",
            "content": f"**TRADER ALERT: {row.get('ticker')}**\nScore **{score:.0f}/100** · ${price:.2f}",
            "embeds": [{"title": f"{row.get('ticker')} · {setup}", "fields": fields}],
        }
        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        sent += 1
    print(f"Discord alerts sent: {sent}")
    return sent


if __name__ == "__main__":
    import pandas as pd
    from scanner import scan
    df = scan(1000, 50)
    send_alerts(df.to_dict(orient="records"))
