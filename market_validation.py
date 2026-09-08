from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scanner import scan


def validate_frame(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {'rows': 0, 'scored': 0, 'missing_scores': 0, 'buy': 0, 'avg_opportunity_score': None, 'action_counts': {}}
    score = pd.to_numeric(frame.get('opportunity_score'), errors='coerce')
    scored = score.dropna()
    actions = frame.get('action', pd.Series(dtype=str)).fillna('NONE').astype(str)
    components = {}
    for name in ['technical', 'fundamentals', 'valuation', 'analysts', 'catalysts', 'institutional', 'macro_sector', 'liquidity_risk']:
        values = pd.to_numeric(frame.get(f'opportunity_{name}_score'), errors='coerce').dropna()
        components[name] = float(values.mean()) if len(values) else None
    return {
        'rows': int(len(frame)),
        'scored': int(len(scored)),
        'missing_scores': int(len(frame) - len(scored)),
        'buy': int((actions == 'BUY').sum()),
        'avg_opportunity_score': float(scored.mean()) if len(scored) else None,
        'min_opportunity_score': float(scored.min()) if len(scored) else None,
        'max_opportunity_score': float(scored.max()) if len(scored) else None,
        'action_counts': {str(k): int(v) for k, v in actions.value_counts().to_dict().items()},
        'component_averages': components,
    }


def run_market_validation() -> tuple[pd.DataFrame, dict]:
    frame = scan(1000, 1000)
    return frame, validate_frame(frame)


def write_outputs(signals: pd.DataFrame, summary: dict, csv_path: str, json_path: str) -> None:
    signals.to_csv(csv_path, index=False)
    Path(json_path).write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    signals, summary = run_market_validation()
    print(json.dumps(summary, indent=2))
    write_outputs(signals, summary, 'market_validation.csv', 'market_validation.json')
