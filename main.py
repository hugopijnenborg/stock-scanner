from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import scanner as scanner_module
from backtest import run_backtest
from market_validation import run_market_validation
from scanner import scan
from score_engine import calculate_score
from universe import load_top_us_stocks

ALERT_THRESHOLD = 80.0
EXCLUDED_TICKERS = {"FLNC"}


def scanner_universe(limit: int | None = None):
    frame = load_top_us_stocks(limit)
    return frame[~frame["ticker"].isin(EXCLUDED_TICKERS)].reset_index(drop=True)


def _json_safe(value):
    """Convert pandas/numpy values to strict JSON-safe Python values."""
    if value is None:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if hasattr(value, "item"):
            return _json_safe(value.item())
    except Exception:
        pass
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def apply_production_score(result):
    """Replace the legacy combined score with the four-part production score."""
    if result is None or result.empty:
        return result
    result = result.copy()
    result["analyst_score"] = result.get("analyst_consensus_score")
    scored = result.apply(calculate_score, axis=1, result_type="expand")
    for column in ["overall_score", "trader_score", "technical_score", "fundamental_score", "analyst_score", "signal"]:
        if column in scored:
            result[column] = scored[column]
    result["trader_similarity_score"] = result["trader_score"]
    return result.sort_values(["overall_score", "trader_score", "technical_score"], ascending=[False, False, False], na_position="last").reset_index(drop=True)


def write_web_output(result, universe_size: int, path: str) -> None:
    rows = result.where(result.notna(), None).to_dict(orient="records")
    rows = [_json_safe(row) for row in rows]
    top_score = None
    if not result.empty and "overall_score" in result:
        top_score = _json_safe(result["overall_score"].max())
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": int(universe_size),
        "alert_count": int((result["signal"] == "ALERT").sum()) if not result.empty and "signal" in result else 0,
        "top_score": top_score,
        "score_weights": {"trader": 35, "technical": 30, "fundamental": 20, "analyst": 15},
        "alert_threshold": 80,
        "results": rows,
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trader-pattern stock scanner")
    sub = parser.add_subparsers(dest="command", required=True)
    u = sub.add_parser("universe", help="show current curated universe")