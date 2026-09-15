from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import scanner as scanner_module
from backtest import run_backtest
from config import ALERT_THRESHOLD, WATCH_THRESHOLD
from market_validation import run_market_validation
from scanner import scan
from universe import load_top_us_stocks

EXCLUDED_TICKERS = {"FLNC"}

# Reflects scanner.py / model.py's assemble_new_score(): Technical
# (dislocation x confirmation) 55%, Fundamentals 30%, Valuation 10%,
# Analyst direction 5%, plus an earnings adjustment and a regime
# multiplier. score_engine.py ("model 4.1", Trader/Technical/Fundamental
# 30/35/35) is retired — it was silently overwriting overall_score and
# signal after scan() ran, so the live app was never actually driven by
# the new methodology despite showing its component breakdown. If you
# still want model 4.1 for comparison, run it as a separate, clearly
# labeled report — never let it touch the fields the live app reads.
MODEL_VERSION = "5.0-technical-fundamentals-valuation-analyst"
SCORE_WEIGHTS = {"technical": 55, "fundamentals": 30, "valuation": 10, "analyst": 5}


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
        "model_version": MODEL_VERSION,
        "score_weights": SCORE_WEIGHTS,
        "alert_threshold": ALERT_THRESHOLD,
        "watch_threshold": WATCH_THRESHOLD,
        "results": rows,
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Technical/Fundamentals/Valuation/Analyst stock scanner")
    sub = parser.add_subparsers(dest="command", required=True)
    u = sub.add_parser("universe", help="show current curated universe")
    u.add_argument("--limit", type=int, default=1000)
    s = sub.add_parser("scan", help="scan current market")
    s.add_argument("--limit", type=int, default=1000)
    s.add_argument("--top", type=int, default=25)
    s.add_argument("--output", default=None)
    s.add_argument("--web-output", default="public/data/latest_scan.json")
    b = sub.add_parser("backtest", help="backtest supplied trader entries")
    b.add_argument("--output", default="trader_backtest.csv")
    v = sub.add_parser("validate-market", help="validate 80+ signals across the full curated universe")
    v.add_argument("--start", default="2024-01-01")
    v.add_argument("--output", default="market_validation.csv")
    v.add_argument("--summary", default="market_validation.json")
    args = parser.parse_args()
    if args.command == "universe":
        print(scanner_universe(args.limit).to_string(index=False))
    elif args.command == "scan":
        scanner_module.load_top_us_stocks = scanner_universe
        universe = scanner_universe(args.limit)
        # scan() is the single source of truth now: it already computes
        # overall_score/signal via assemble_new_score() and already holds
        # first-time ALERTs back to WATCH until a second scan confirms them
        # (see scanner.py's _new_signal() / data/pending_confirmations.json).
        # No post-processing step here anymore.
        result = scan(args.limit, args.top)
        print(result.to_string(index=False))
        if args.output:
            result.to_csv(args.output, index=False)
            print(f"\nSaved {args.output}")
        write_web_output(result, len(universe), args.web_output)
        print(f"Saved {args.web_output}")
    elif args.command == "backtest":
        result = run_backtest()
        print(result.to_string(index=False))
        result.to_csv(args.output, index=False)
        print(f"\nSaved {args.output}")
    elif args.command == "validate-market":
        signals, summary = run_market_validation(args.start)
        print(json.dumps(summary, indent=2))
        signals.to_csv(args.output, index=False)
        Path(args.summary).write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
        print(f"Saved {args.output} and {args.summary}")


if __name__ == "__main__":
    main()
