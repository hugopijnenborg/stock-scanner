import pandas as pd

from walk_forward_validation import build_trade_events


def test_trade_events_use_first_80_and_60_day_cooldown():
    df = pd.DataFrame([
        {"date": "2026-01-02", "ticker": "AAA", "score": 82, "return_1d": 0.01, "return_5d": 0.02, "return_10d": 0.03, "return_20d": 0.05, "return_30d": 0.06, "return_60d": 0.08, "max_gain_60d": 0.12, "max_drawdown_60d": -0.05},
        {"date": "2026-01-05", "ticker": "AAA", "score": 88, "return_1d": 0.01, "return_5d": 0.02, "return_10d": 0.03, "return_20d": 0.05, "return_30d": 0.06, "return_60d": 0.08, "max_gain_60d": 0.12, "max_drawdown_60d": -0.05},
        {"date": "2026-02-20", "ticker": "AAA", "score": 91, "return_1d": 0.01, "return_5d": 0.02, "return_10d": 0.03, "return_20d": 0.05, "return_30d": 0.06, "return_60d": 0.08, "max_gain_60d": 0.12, "max_drawdown_60d": -0.05},
        {"date": "2026-03-10", "ticker": "AAA", "score": 83, "return_1d": 0.01, "return_5d": 0.02, "return_10d": 0.03, "return_20d": 0.05, "return_30d": 0.06, "return_60d": 0.08, "max_gain_60d": 0.12, "max_drawdown_60d": -0.05},
        {"date": "2026-03-15", "ticker": "BBB", "score": 90, "return_1d": 0.01, "return_5d": 0.02, "return_10d": 0.03, "return_20d": 0.05, "return_30d": 0.06, "return_60d": 0.08, "max_gain_60d": 0.12, "max_drawdown_60d": -0.05},
    ])
    events = build_trade_events(df)
    aaa = events[events["ticker"] == "AAA"]
    assert len(aaa) == 2
    assert aaa.iloc[0]["entry_score"] == 82
    assert aaa.iloc[0]["peak_score_60d"] == 91
    assert aaa.iloc[0]["days_to_85"] == 3
    assert aaa.iloc[0]["days_to_90"] == 49
    assert aaa.iloc[1]["entry_score"] == 83
    assert len(events[events["ticker"] == "BBB"]) == 1
