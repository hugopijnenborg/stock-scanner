from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from backtest import run_backtest
from market_validation import run_market_validation
from scanner import scan
from universe import load_top_us_stocks


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
        value = result["overall_score"].max()
        top_score = _json_safe(value)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": int(universe_size),
        "alert_count": int((result["signal"] == "ALERT").sum()) if not result.empty and "signal" in result else 0,
        "top_score": top_score,
        "results": rows,
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trader-pattern stock scanner")
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
        print(load_top_us_stocks(args.limit).to_string(index=False))
    elif args.command == "scan":
        universe = load_top_us_stocks(args.limit)
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
