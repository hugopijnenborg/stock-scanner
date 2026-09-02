import pandas as pd

from walk_forward_validation import forward_metrics


def test_forward_metrics_uses_trading_days_for_short_horizons_and_calendar_days_for_60d():
    index = pd.bdate_range("2026-01-02", "2026-04-30")
    close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)

    result = forward_metrics(close, pd.Timestamp("2026-01-02"))

    assert result["return_1d"] == close.iloc[1] / close.iloc[0] - 1
    assert result["return_5d"] == close.iloc[5] / close.iloc[0] - 1

    target_day = pd.Timestamp("2026-01-02") + pd.Timedelta(days=60)
    target_pos = next(i for i, day in enumerate(index) if day >= target_day)
    assert result["return_60d"] == close.iloc[target_pos] / close.iloc[0] - 1


def test_forward_metrics_60d_is_not_40_trading_days():
    index = pd.bdate_range("2026-01-02", "2026-04-30")
    close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)

    result = forward_metrics(close, pd.Timestamp("2026-01-02"))
    forty_trading_return = close.iloc[40] / close.iloc[0] - 1

    assert result["return_60d"] != forty_trading_return
