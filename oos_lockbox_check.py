"""Out-of-sample lockbox check.

Every other validation script in this repo (walk_forward_validation.py,
market_validation.py) trains and tests on overlapping data: the same
trader entries that get used to pick thresholds/weights are also the
ones the winrate numbers are calculated from. This script is different
on purpose: it holds back the most recent trader entries, trains a model
that has never seen them, and only then scores them.

Do NOT use this script's results to tune weights or thresholds. That
would defeat the point — the moment you adjust something because the
lockbox result disappointed you, it stops being out-of-sample. Run it,
read it, and only revisit the model/scoring code based on it if you're
willing to re-lock a fresh, later holdout afterwards.

This makes real network calls (yfinance) and needs the learn_model.py /
backtest.py / model.py machinery already in this repo. Run it locally or
via workflow_dispatch, not as a scheduled job.

Usage:
    python oos_lockbox_check.py --holdout-days 90
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from backtest import load_entries, run_backtest, TRADER_HISTORY_PATH
from learn_model import train as train_learned_model

LOCKBOX_MODEL_PATH = Path("learned_model_lockbox.json")
LIVE_MODEL_PATH = Path("learned_model.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train on trader entries before a cutoff, then score the held-out entries after it.")
    parser.add_argument("--holdout-days", type=int, default=90, help="Hold out trader entries from the last N days.")
    args = parser.parse_args()

    entries = load_entries(TRADER_HISTORY_PATH)
    cutoff = entries["date"].max() - pd.Timedelta(days=args.holdout_days)
    locked = entries[entries["date"] >= cutoff]
    trainable = entries[entries["date"] < cutoff]
    print(f"Cutoff: {cutoff.date()}. Training on {len(trainable)} entries, locking away {len(locked)} entries after cutoff.")
    if len(locked) == 0:
        print("No entries fall after the cutoff — nothing to lock away. Reduce --holdout-days or add more recent trades.")
        return
    if len(trainable) < 10:
        print(f"Only {len(trainable)} trainable entries left before cutoff — too few to train on (need >=10). Reduce --holdout-days.")
        return

    print("Training lockbox model (never sees the held-out entries)...")
    train_learned_model(output=str(LOCKBOX_MODEL_PATH), cutoff=cutoff)

    # Temporarily point model.py's learned-model loader at the lockbox
    # model so run_backtest() scores the locked entries with a model that
    # has genuinely never seen them, then restore the live model file.
    live_backup = None
    if LIVE_MODEL_PATH.exists():
        live_backup = LIVE_MODEL_PATH.read_bytes()
    shutil.copy(LOCKBOX_MODEL_PATH, LIVE_MODEL_PATH)
    try:
        locked.to_csv("_lockbox_entries.csv", index=False)
        result = run_backtest(path="_lockbox_entries.csv")
    finally:
        if live_backup is not None:
            LIVE_MODEL_PATH.write_bytes(live_backup)
        else:
            LIVE_MODEL_PATH.unlink(missing_ok=True)
        Path("_lockbox_entries.csv").unlink(missing_ok=True)

    result.to_csv("oos_lockbox_result.csv", index=False)
    cols = ["date", "ticker", "price", "trader_similarity_score", "technical_opportunity_score", "return_5d", "return_20d", "return_60d"]
    cols = [c for c in cols if c in result.columns]
    print("\n=== Held-out entries, scored by a model that never saw them ===")
    print(result[cols].to_string(index=False))
    print("\nSaved oos_lockbox_result.csv and learned_model_lockbox.json.")
    print("Reminder: do not tune anything off this result without re-locking a fresh holdout afterwards.")


if __name__ == "__main__":
    main()
