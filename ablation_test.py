"""Ablation test: does the trader-pattern component add real signal?

Runs walk_forward_validation.run() twice on identical data:
  - trader_weight=0.00  -> pure technical/oversold score (baseline)
  - trader_weight=0.70  -> the live formula (trader + technical)

If the live formula does not clearly beat the pure-technical baseline on
winrate and average return at the 80+ threshold, the trader-pattern
component is not earning its 70% weight and should not be trusted as the
core of the scanner without further investigation.

This makes real network calls (yfinance) and takes as long as a normal
walk-forward run, twice. Run it locally or via `workflow_dispatch` —
it is not wired into a scheduled workflow on purpose, since it's a
one-off diagnostic, not something that needs to run every day.

Usage:
    python ablation_test.py
"""
from __future__ import annotations

import json

from walk_forward_validation import run

BASELINE_WEIGHT = 0.00  # pure technical, no trader pattern
LIVE_WEIGHT = 0.70      # matches scanner.py / model.py score_row()
KEY_THRESHOLD = "80"
KEY_HORIZONS = ["5d", "20d", "60d"]


def _extract(summary: dict, threshold: str, horizon: str) -> dict:
    stats = summary.get("thresholds", {}).get(threshold, {})
    return {
        "n": stats.get(f"n_{horizon}"),
        "winrate": stats.get(f"winrate_{horizon}"),
        "avg_return": stats.get(f"avg_return_{horizon}"),
    }


def main() -> None:
    print(f"Running baseline (trader_weight={BASELINE_WEIGHT}, pure technical)...")
    baseline = run(
        output_csv="ablation_baseline.csv",
        summary_json="ablation_baseline.json",
        trader_weight=BASELINE_WEIGHT,
    )

    print(f"Running live formula (trader_weight={LIVE_WEIGHT})...")
    live = run(
        output_csv="ablation_live.csv",
        summary_json="ablation_live.json",
        trader_weight=LIVE_WEIGHT,
    )

    print("\n=== Ablation result: threshold 80+, by horizon ===")
    print(f"{'horizon':<8}{'baseline N':<12}{'baseline WR':<14}{'baseline avg':<14}"
          f"{'live N':<10}{'live WR':<12}{'live avg':<12}{'WR delta':<10}{'avg delta':<10}")
    rows = []
    for horizon in KEY_HORIZONS:
        b = _extract(baseline, KEY_THRESHOLD, horizon)
        l = _extract(live, KEY_THRESHOLD, horizon)
        wr_delta = (l["winrate"] - b["winrate"]) if l["winrate"] is not None and b["winrate"] is not None else None
        avg_delta = (l["avg_return"] - b["avg_return"]) if l["avg_return"] is not None and b["avg_return"] is not None else None
        rows.append({"horizon": horizon, "baseline": b, "live": l, "winrate_delta": wr_delta, "avg_return_delta": avg_delta})
        print(
            f"{horizon:<8}{str(b['n']):<12}{_fmt_pct(b['winrate']):<14}{_fmt_pct(b['avg_return']):<14}"
            f"{str(l['n']):<10}{_fmt_pct(l['winrate']):<12}{_fmt_pct(l['avg_return']):<12}"
            f"{_fmt_pct(wr_delta):<10}{_fmt_pct(avg_delta):<10}"
        )

    print(
        "\nRead this as: if winrate_delta and avg_return_delta are small or negative "
        "at 20D/60D, the trader-pattern component is not clearly adding value over "
        "pure technical oversold conditions at its current 70% weight."
    )
    with open("ablation_comparison.json", "w", encoding="utf-8") as f:
        json.dump({"baseline_weight": BASELINE_WEIGHT, "live_weight": LIVE_WEIGHT, "comparison": rows}, f, indent=2)
    print("\nSaved ablation_comparison.json, ablation_baseline.json, ablation_live.json")


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.1f}%"


if __name__ == "__main__":
    main()
