from __future__ import annotations
import os
from typing import Any
import requests

def send_alerts(results: list[dict[str, Any]], webhook_url: str | None = None) -> int:
    webhook_url = webhook_url or os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print('DISCORD_WEBHOOK_URL not configured; skipping Discord alerts')
        return 0
    alerts = sorted([r for r in results if r.get('action') == 'BUY' and r.get('should_alert', True)], key=lambda r: float(r.get('opportunity_score', 0) or 0), reverse=True)[:10]
    sent = 0
    for row in alerts:
        score = float(row.get('opportunity_score', 0) or 0)
        price = float(row.get('price', 0) or 0)
        confidence = float(row.get('confidence', 0) or 0)
        rr = row.get('risk_reward')
        fields = [
            {'name': 'Setup', 'value': str(row.get('setup_type', 'unknown')), 'inline': True},
            {'name': 'Confidence', 'value': f'{confidence / 10:.1f}/10', 'inline': True},
            {'name': 'Risk / Reward', 'value': f'{float(rr):.1f} : 1' if rr is not None else '—', 'inline': True},
            {'name': '5D', 'value': f"{float(row.get('return_5d', 0) or 0) * 100:.1f}%", 'inline': True},
            {'name': 'Reversal', 'value': f"{float(row.get('reversal_confirmation', 0) or 0) * 100:.0f}/100", 'inline': True},
        ]
        reasons = row.get('reasons') or []
        content = f"**BUY ALERT: {row.get('ticker')}**\nOpportunity Score **{score:.1f}/100** · ${price:.2f}"
        if reasons:
            content += f"\n{reasons[0]}"
        payload = {'username': 'MarketIntel Opportunity Scanner', 'content': content, 'embeds': [{'title': f"{row.get('ticker')} · {row.get('setup_type', 'Opportunity')}", 'fields': fields}]}
        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        sent += 1
    print(f'Discord BUY alerts sent: {sent}')
    return sent

if __name__ == '__main__':
    from scanner import scan
    df = scan(1000, 50)
    send_alerts(df.to_dict(orient='records'))
