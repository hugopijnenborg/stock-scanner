"""The scan log is the measurement base for judging the scanner.

Only alerts were ever recorded, so there was no control group: nothing to
compare a scoring 85 against. These checks keep the full-universe log honest.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("log_scan_snapshot", REPO / "scripts" / "log_scan_snapshot.py")
logger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(logger)


SCAN = {
    "generated_at": "2026-09-15T07:31:31+00:00",
    "model_version": "3.0",
    "results": [
        {
            "ticker": "CRDO", "company_name": "Credo Technology", "price": 149.97,
            "overall_score": 81.0, "trader_score": 83.0, "technical_score": 68.0,
            "fundamental_score": 92.0, "signal": "ALERT", "rsi_14": 30.15,
            "return_5d": -0.12, "return_20d": -0.42, "distance_52w_high": -0.50,
            "distance_sma50": -0.32, "volume_ratio": 1.42,
        },
        {
            "ticker": "AAPL", "company_name": "Apple", "price": 220.0,
            "overall_score": 41.2, "trader_score": 40.0, "technical_score": 35.0,
            "fundamental_score": 48.0, "signal": "NO_SIGNAL", "rsi_14": None,
            "return_5d": float("nan"), "return_20d": 0.03, "distance_52w_high": -0.02,
            "distance_sma50": 0.01, "volume_ratio": 0.9,
        },
        {"company_name": "geen ticker"},
    ],
}


def test_every_scanned_row_is_logged_not_only_the_alerts():
    rows = logger.build_rows(SCAN)
    assert [r["ticker"] for r in rows] == ["CRDO", "AAPL"]
    assert {r["signal"] for r in rows} == {"ALERT", "NO_SIGNAL"}


def test_rows_carry_the_model_version_and_scan_time():
    for row in logger.build_rows(SCAN):
        assert row["model_version"] == "3.0"
        assert row["scan_generated_at"] == SCAN["generated_at"]


def test_raw_components_are_kept_so_other_weightings_can_be_tested_later():
    crdo = logger.build_rows(SCAN)[0]
    for column in ("trader_score", "technical_score", "fundamental_score", "overall_score"):
        assert crdo[column] is not None
    for column in ("distance_52w_high", "rsi_14", "return_20d", "volume_ratio"):
        assert column in crdo


def test_non_finite_numbers_become_null_so_the_insert_does_not_fail():
    aapl = logger.build_rows(SCAN)[1]
    assert aapl["return_5d"] is None
    assert aapl["rsi_14"] is None


def test_a_scan_without_a_model_version_is_refused():
    with pytest.raises(ValueError):
        logger.build_rows({"generated_at": "2026-09-15T07:31:31+00:00", "results": []})


def test_logged_columns_all_exist_in_the_table_migration():
    """Guard against adding a field here that the database has no column for."""
    rows = logger.build_rows(SCAN)
    expected = {
        "scan_generated_at", "model_version", "ticker", "company_name", "price",
        "overall_score", "trader_score", "technical_score", "fundamental_score",
        "signal", "rsi_14", "return_5d", "return_20d", "distance_52w_high",
        "distance_sma50", "volume_ratio",
    }
    assert set(rows[0]) == expected
