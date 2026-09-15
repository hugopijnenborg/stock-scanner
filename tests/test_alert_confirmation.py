"""A score of 80+ that clears the gate and R/R fires ALERT immediately.

The two-scan confirmation this used to require (a first hit held as WATCH
until a second scan agreed) was removed on request: the user wants an
80+ read as a buy the moment it happens, not one cycle later. That trades
away the noise-filtering the confirmation step gave — a ticker hovering
right at 80 can now alert then drop back below it 15 minutes later — for
not missing a fast-moving setup. Kept as its own test file (same name) so
the intent stays documented rather than just disappearing.
"""
from __future__ import annotations

from scanner import _new_signal


def test_a_qualifying_score_alerts_immediately():
    assert _new_signal(overall=84.0, gate_excluded=False, risk_reward_value=2.5) == "ALERT"


def test_watch_band_is_unaffected():
    assert _new_signal(overall=68.0, gate_excluded=False, risk_reward_value=None) == "WATCH"


def test_below_watch_threshold_is_no_signal():
    assert _new_signal(overall=32.0, gate_excluded=False, risk_reward_value=None) == "NO_SIGNAL"


def test_gate_exclusion_blocks_alert_even_at_a_high_score():
    assert _new_signal(overall=88.0, gate_excluded=True, risk_reward_value=2.5) == "WATCH"


def test_weak_risk_reward_blocks_alert_even_at_a_high_score():
    assert _new_signal(overall=90.0, gate_excluded=False, risk_reward_value=1.2) == "WATCH"


def test_missing_score_is_data_incomplete():
    assert _new_signal(overall=None, gate_excluded=False, risk_reward_value=None) == "DATA_INCOMPLETE"
