from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

SCAN = Path('public/data/latest_scan.json')
HISTORY = Path('public/data/alert_history.json')

HORIZONS = {1: '1D', 5: '5D', 10: '10D', 20: '20D'}

def load_json(path):
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return {}

def main():
    scan = load_json(SCAN)
    rows = scan.get('results', [])
    history = load_json(HISTORY)
    alerts = history.get('alerts', [])
    existing = {(x.get('ticker'), x.get('alert_date')) for x in alerts}
    today = datetime.now(timezone.utc).date().isoformat()

    for r in rows:
        if r.get('signal') != 'ALERT': continue
        key = (r.get('ticker'), today)
        if key not in existing:
            alerts.append({
                'ticker': r.get('ticker'), 'company_name': r.get('company_name'),
                'alert_date': today, 'alert_price': r.get('price'),
                'score': r.get('overall_score'), 'trader_score': r.get('trader_similarity_score'),
                'technical_score': r.get('technical_score'), 'fundamental_score': r.get('fundamental_score'),
                'returns': {}
            })

    for a in alerts:
        try:
            start = pd.Timestamp(a['alert_date'])
            end = pd.Timestamp.now() + pd.Timedelta(days=2)
            hist = yf.download(a['ticker'], start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), auto_adjust=False, progress=False)
            if hist.empty: continue
            close = hist['Close']
            if hasattr(close, 'columns'): close = close.iloc[:,0]
            prices = close.dropna().tolist()
            if not prices: continue
            entry = float(a.get('alert_price') or prices[0])
            for n,label in HORIZONS.items():
                if len(prices) > n:
                    a['returns'][label] = round((float(prices[n]) / entry - 1) * 100, 2)
        except Exception:
            continue

    out = {'updated_at': datetime.now(timezone.utc).isoformat(), 'alerts': sorted(alerts, key=lambda x: x.get('alert_date',''), reverse=True)}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(out, indent=2, allow_nan=False), encoding='utf-8')

if __name__ == '__main__': main()
