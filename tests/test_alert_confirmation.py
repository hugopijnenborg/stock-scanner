"""A first-time alert waits for a second scan to agree with it.

The scanner rescores every fifteen minutes on a day bar that is still forming,
so a ticker sitting near the threshold can alert at 16:00 and fall back at
16:15. One confirming scan costs a quarter of an hour and removes the alerts
that only existed because of where the bar happened to be at that moment.
"""

from __future__ import annotations

import pandas as pd

from main import confirm_alerts


def frame(rows):
    return pd.DataFrame(rows)


def test_a_first_time_alert_is_held_as_watch():
    result = confirm_alerts(
        frame([{"ticker": "CRDO", "overall_score": 84.0, "signal": "ALERT"}]),
        previous={"CRDO": 71.0},
    )
    assert result.loc[0, "signal"] == "WATCH"
    assert bool(result.loc[0, "alert_confirmed"]) is False


def test_an_alert_the_previous_scan_also_had_goes_through():
    result = confirm_alerts(
        frame([{"ticker": "CRDO", "overall_score": 84.0, "signal": "ALERT"}]),
        previous={"CRDO": 82.5},
    )
    assert result.loc[0, "signal"] == "ALERT"
    assert bool(result.loc[0, "alert_confirmed"]) is True


def test_a_ticker_that_dipped_below_the_line_must_requalify():
    """79.9 in the previous scan is not confirmation, however close it looks."""
    result = confirm_alerts(
        frame([{"ticker": "WDC", "overall_score": 80.4, "signal": "ALERT"}]),
        previous={"WDC": 79.9},
    )
    assert result.loc[0, "signal"] == "WATCH"


def test_watch_and_no_signal_rows_are_untouched():
    result = confirm_alerts(
        frame([
            {"ticker": "VRT", "overall_score": 68.0, "signal": "WATCH"},
            {"ticker": "HON", "overall_score": 32.0, "signal": "NO_SIGNAL"},
        ]),
        previous={"VRT": 70.0, "HON": 30.0},
    )
    assert list(result["signal"]) == ["WATCH", "NO_SIGNAL"]


def test_the_first_scan_after_a_deploy_is_not_swallowed():
    """With no previous scan there is nothing to confirm against."""
    result = confirm_alerts(
        frame([{"ticker": "CRDO", "overall_score": 84.0, "signal": "ALERT"}]),
        previous={},
    )
    assert result.loc[0, "signal"] == "ALERT"


def test_a_ticker_absent_from_the_previous_scan_is_held():
    result = confirm_alerts(
        frame([{"ticker": "NEW", "overall_score": 88.0, "signal": "ALERT"}]),
        previous={"CRDO": 85.0},
    )
    assert result.loc[0, "signal"] == "WATCH"


def test_an_empty_scan_is_handled():
    assert confirm_alerts(pd.DataFrame(), previous={"CRDO": 85.0}).empty
