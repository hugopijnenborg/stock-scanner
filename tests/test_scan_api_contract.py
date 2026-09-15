"""Guards the contract between score_engine.py and the /api/scan route.

The score is calculated once, in score_engine.py, and published inside
public/data/latest_scan.json. The Next.js route must pass those numbers
through untouched. When the route recalculated the score it re-applied the
trader/technical relaxation to already-relaxed values, which pushed sub-80
rows over the 80 BUY ALERT threshold in the browser while the backend still
called them WATCH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from score_engine import MODEL_VERSION

REPO = Path(__file__).resolve().parents[1]
ROUTE = REPO / "app" / "api" / "scan" / "route.js"
SCAN = REPO / "public" / "data" / "latest_scan.json"

ALERT_THRESHOLD = 80.0
WATCH_THRESHOLD = 50.0


def expected_signal(overall):
    if overall is None:
        return "DATA_INCOMPLETE"
    if overall >= ALERT_THRESHOLD:
        return "ALERT"
    if overall >= WATCH_THRESHOLD:
        return "WATCH"
    return "NO_SIGNAL"


@pytest.fixture(scope="module")
def payload():
    """The most recently published scan, only if it came from this model.

    Scores from different model versions are not comparable, so a scan
    published by an older version is skipped rather than asserted against.
    The next scan republishes the file and these checks go live again.
    """
    data = json.loads(SCAN.read_text(encoding="utf-8"))
    published = data.get("model_version")
    if published != MODEL_VERSION:
        pytest.skip(
            f"published scan is model {published!r}, this code is {MODEL_VERSION!r}; "
            "re-run the scanner to refresh public/data/latest_scan.json"
        )
    return data


def test_route_does_not_recalculate_the_score():
    source = ROUTE.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("//")
    )
    for forbidden in ("RELAXATION", "relaxScore", "trader_similarity_score *", "* WEIGHTS"):
        assert forbidden not in code, (
            f"{ROUTE.name} contains {forbidden!r}. The route must not score rows: "
            "the published trader/technical values are already calibrated and "
            "scoring them again applies the relaxation twice."
        )
    assert "row.overall_score" in code, "the route must pass through the published score"


def test_published_scan_uses_the_production_contract(payload):
    assert payload["alert_threshold"] == 80
    assert payload["score_weights"] == {"trader": 30, "technical": 35, "fundamental": 35}


def test_published_score_is_the_plain_weighted_sum(payload):
    """No component may be rescaled on its way into the published score."""
    checked = 0
    for row in payload["results"]:
        parts = [
            (row.get("trader_score"), 0.30),
            (row.get("technical_score"), 0.35),
            (row.get("fundamental_score"), 0.35),
        ]
        usable = [(v, w) for v, w in parts if v is not None]
        if not usable:
            continue
        weight_sum = sum(w for _, w in usable)
        expected = sum(v * w for v, w in usable) / weight_sum
        assert row["overall_score"] == pytest.approx(expected, abs=0.05), (
            f"{row['ticker']}: published {row['overall_score']} but the three "
            f"components weigh out to {expected:.1f}"
        )
        checked += 1
    assert checked > 50, "too few complete rows to verify the formula"


def test_published_signals_match_the_80_threshold(payload):
    for row in payload["results"]:
        overall = row.get("overall_score")
        assert row["signal"] == expected_signal(overall), (
            f"{row['ticker']} has score {overall} but signal {row['signal']}"
        )
        if row["signal"] == "ALERT":
            assert overall >= ALERT_THRESHOLD


def test_published_alert_count_matches_the_rows(payload):
    counted = sum(1 for row in payload["results"] if row["signal"] == "ALERT")
    assert payload["alert_count"] == counted


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_route_returns_the_same_scores_as_the_backend(payload):
    """Run the real route code and compare it row by row with the published scan."""
    source = ROUTE.read_text(encoding="utf-8")
    harness = "\n".join(
        line for line in source.splitlines() if "next/server" not in line
    )
    harness += """
import { readFileSync } from 'node:fs';
const rows = JSON.parse(readFileSync(process.argv[2], 'utf8'));
process.stdout.write(JSON.stringify(rows.map(normalizeResult)));
"""
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "route_harness.mjs"
        script.write_text(harness, encoding="utf-8")
        rows_file = Path(tmp) / "rows.json"
        rows_file.write_text(json.dumps(payload["results"]), encoding="utf-8")
        completed = subprocess.run(
            ["node", str(script), str(rows_file)],
            capture_output=True,
            text=True,
            check=True,
        )
    normalized = json.loads(completed.stdout)

    assert len(normalized) == len(payload["results"])
    for published, served in zip(payload["results"], normalized):
        assert served["ticker"] == published["ticker"]
        assert served["overall_score"] == published["overall_score"], (
            f"{published['ticker']}: route returns {served['overall_score']} "
            f"but the backend published {published['overall_score']}"
        )
        assert served["signal"] == published["signal"]

    served_alerts = sum(1 for row in normalized if row["signal"] == "ALERT")
    assert served_alerts == payload["alert_count"]
