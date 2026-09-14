from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import scanner as scanner_module
from backtest import run_backtest
from market_validation import run_market_validation
from opportunity_engine import WEIGHTS, apply_opportunity_engine
from scanner import scan
from universe import load_top_us_stocks

ALERT_THRESHOLD = 80.0
WATCH_THRESHOLD = 65.0
EXCLUDED_TICKERS = {"FLNC"}
SCORE_CURVE_EXPONENT = 0.80
SCORE_EXPANSION_SLOPE = 1.40
SCORE_EXPANSION_OFFSET = 7.5


def scanner_universe(limit: int | None = None):
    frame = load_top_us_stocks(limit)
    return frame[~frame["ticker"].isin(EXCLUDED_TICKERS)].reset_index(drop=True)


def _json_safe(value):
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


def _calibrate_component(value):
    if value is None or not math.isfinite(float(value)):
        return None
    x = max(0.0, min(100.0, float(value))) / 100.0
    return round((x ** SCORE_CURVE_EXPONENT) * 100.0, 1)


def apply_production_score(result):
    """Apply the 2.4 opportunity model with a deliberately broader 0-100 score distribution."""
    if result is None or result.empty:
        return result

    result = apply_opportunity_engine(result.copy())

    calibrated = {
        component: result[f"opportunity_{component}_score"].apply(_calibrate_component)
        for component in WEIGHTS
    }
    data_quality = pd.to_numeric(result.get("data_quality", 1.0), errors="coerce").fillna(1.0).clip(0, 1)
    quality_factor = 0.90 + 0.10 * data_quality

    weighted = sum(calibrated[k] * WEIGHTS[k] / 100.0 for k in WEIGHTS)
    base_score = (weighted * quality_factor).round(1)

    # The previous curve compressed the opportunity distribution too heavily.
    # Expand the final score so a genuinely strong market pullback can produce
    # several 70-85 scores instead of clustering everything in the 40s-60s.
    result["overall_score_base"] = base_score
    result["overall_score"] = (base_score * SCORE_EXPANSION_SLOPE + SCORE_EXPANSION_OFFSET).clip(0, 100).round(1)

    # Keep the existing UI data contract intact. The visible component values
    # remain the calibrated 2.4 components, while the total uses all eight 2.4
    # components and their original weights before the score expansion.
    result["technical_score"] = calibrated["technical"]
    result["fundamental_score"] = calibrated["fundamentals"]
    result["analyst_consensus_score"] = calibrated["analysts"]
    context_weight = sum(WEIGHTS[k] for k in ("valuation", "catalysts", "institutional", "macro_sector", "liquidity_risk"))
    result["context_score"] = (
        sum(calibrated[k] * WEIGHTS[k] for k in ("valuation", "catalysts", "institutional", "macro_sector", "liquidity_risk"))
        / context_weight
    ).round(1)
    result["trader_similarity_score"] = result["context_score"]

    result["signal"] = result["overall_score"].apply(
        lambda x: "ALERT" if x >= ALERT_THRESHOLD else "WATCH" if x >= WATCH_THRESHOLD else "NO_SIGNAL"
    )
    result["qualifies_new_buy"] = result["signal"].eq("ALERT")
    result["action"] = result["signal"].map({"ALERT": "BUY", "WATCH": "NONE", "NO_SIGNAL": "NONE"}).fillna("NONE")
    result["alert_summary"] = result.apply(
        lambda r: scanner_module._alert_summary(r) if r["signal"] == "ALERT" else None,
        axis=1,
    )
    return result.sort_values(["overall_score", "technical_score"], ascending=[False, False], na_position="last").reset_index(drop=True)


def write_web_output(result, universe_size: int, path: str) -> None:
    rows = result.where(result.notna(), None).to_dict(orient="records")
    rows = [_json_safe(row) for row in rows]
    top_score = None
    if not result.empty and "overall_score" in result:
        top_score = _json_safe(result["overall_score"].max())
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": int(universe_size),
        "alert_count": int((result["signal"] == "ALERT").sum()) if not result.empty else 0,
        "top_score": top_score,
        "score_weights": {"technical": 30, "fundamentals": 20, "analysts": 15, "context": 35},
        "alert_threshold": ALERT_THRESHOLD,
        "score_curve_exponent": SCORE_CURVE_EXPONENT,
        "score_expansion": {"slope": SCORE_EXPANSION_SLOPE, "offset": SCORE_EXPANSION_OFFSET},
        "results": rows,
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock opportunity scanner")
    sub = parser.add_subparsers(dest="command", required=True)
    u = sub.add_parser("universe", help="show current curated universe")
    u.add_argument("--limit", type=int, default=1000)
    s = sub.add_parser("scan", help="scan current market")
    s.add_argument("--limit", type=int, default=1000)
    s.add_argument("--top", type=int, default=1000)
    s.add_argument("--output", default=None)
    s.add_argument("--web-output", default="public/data/latest_scan.json")
    b = sub.add_parser("backtest", help="backtest supplied trader entries")
    b.add_argument("--output", default="trader_backtest.csv")
    v = sub.add_parser("validate-market", help="validate signals across the full curated universe")
    v.add_argument("--start", default="2024-01-01")
    v.add_argument("--output", default="market_validation.csv")
    v.add_argument("--summary", default="market_validation.json")
    args = parser.parse_args()

    if args.command == "universe":
        print(scanner_universe(args.limit).to_string(index=False))
    elif args.command == "scan":
        scanner_module.load_top_us_stocks = scanner_universe
        universe = scanner_universe(args.limit)
        result = apply_production_score(scan(args.limit, max(args.top, 1000)))
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
