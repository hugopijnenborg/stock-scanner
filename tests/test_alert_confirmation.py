"""A first-time alert waits for a second scan to agree with it.

This now lives in scanner.py's _new_signal() / data/pending_confirmations.json
rather than main.py's confirm_alerts(), which was model 4.1's separate,
redundant confirmation gate and has been removed along with the rest of
model 4.1 (score_engine.py). Same behaviour, single source of truth.
"""
from __future__ import annotations

from scanner import _new_signal


def test_a_first_time_alert_is_held_as_watch():
    assert _new_signal(overall=84.0, gate_excluded=False, risk_reward_value=2.5, confirmed=False) == "WATCH"


def test_an_alert_confirmed_by_the_previous_scan_goes_through():
    assert _new_signal(overall=84.0, gate_excluded=False, risk_reward_value=2.5, confirmed=True) == "ALERT"


def test_watch_rows_are_unaffected_by_confirmation():
    assert _new_signal(overall=68.0, gate_excluded=False, risk_reward_value=None, confirmed=False) == "WATCH"
    assert _new_signal(overall=68.0, gate_excluded=False, risk_reward_value=None, confirmed=True) == "WATCH"


def test_no_signal_rows_are_unaffected_by_confirmation():
    assert _new_signal(overall=32.0, gate_excluded=False, risk_reward_value=None, confirmed=False) == "NO_SIGNAL"


def test_gate_exclusion_blocks_alert_even_when_confirmed():
    assert _new_signal(overall=88.0, gate_excluded=True, risk_reward_value=2.5, confirmed=True) == "WATCH"


def test_weak_risk_reward_blocks_alert_even_when_confirmed():
    assert _new_signal(overall=90.0, gate_excluded=False, risk_reward_value=1.2, confirmed=True) == "WATCH"


def test_missing_score_is_data_incomplete():
    assert _new_signal(overall=None, gate_excluded=False, risk_reward_value=None, confirmed=False) == "DATA_INCOMPLETE"
