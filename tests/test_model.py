from opportunity_engine import (
    calculate_opportunity_score,
    reversal_confirmation,
    score_analysts,
    score_technical,
    _classify_setup,
)


def test_opportunity_score_uses_weights_and_is_bounded():
    components = {k: 50.0 for k in ["technical", "fundamentals", "valuation", "analysts", "catalysts", "institutional", "macro_sector", "liquidity_risk"]}
    assert calculate_opportunity_score(components, 1.0) == 50.0
    high = {k: 100.0 for k in components}
    assert calculate_opportunity_score(high, 1.0) == 100.0


def test_opportunity_score_has_data_quality_haircut():
    components = {k: 90.0 for k in ["technical", "fundamentals", "valuation", "analysts", "catalysts", "institutional", "macro_sector", "liquidity_risk"]}
    assert calculate_opportunity_score(components, 1.0) == 90.0
    assert calculate_opportunity_score(components, 0.0) == 81.0


def test_reversal_confirmation_requires_dislocation():
    row = {
        "close_location": 0.90,
        "return_1d": 0.02,
        "return_5d": 0.10,
        "return_20d": 0.12,
        "distance_52w_high": -0.02,
        "macd_histogram_change": 0.20,
        "macd_histogram": -0.10,
        "intraday_score": 90,
    }
    value = reversal_confirmation(row)
    assert 0 <= value <= 0.05


def test_reversal_confirmation_can_be_strong_after_selloff():
    row = {
        "close_location": 0.92,
        "return_1d": 0.05,
        "return_5d": -0.10,
        "return_20d": -0.18,
        "distance_52w_high": -0.25,
        "macd_histogram_change": 0.03,
        "macd_histogram": -0.02,
        "intraday_score": 85,
    }
    value = reversal_confirmation(row)
    assert 0.0 <= value <= 1.0
    assert value > 0.10


def test_technical_score_is_bounded():
    row = {
        "return_1d": 0.02,
        "return_5d": -0.12,
        "return_20d": -0.20,
        "distance_52w_high": -0.20,
        "rsi_14": 32,
        "volume_ratio": 2.0,
        "distance_support_20d": 0.02,
        "distance_support_60d": 0.03,
        "distance_support_120d": 0.04,
        "distance_sma20": -0.08,
        "distance_sma50": -0.10,
        "distance_sma200": -0.05,
        "sector_relative_strength_20d": 0.05,
        "close_location": 0.8,
        "macd_histogram_change": 0.03,
        "macd_histogram": -0.02,
        "intraday_score": 80,
    }
    score, reversal = score_technical(row)
    assert 0 <= score <= 100
    assert 0 <= reversal <= 1


def test_recent_winner_does_not_get_high_technical_score_from_momentum():
    row = {
        "return_1d": 0.02,
        "return_5d": 0.10,
        "return_20d": 0.12,
        "distance_52w_high": -0.02,
        "rsi_14": 62,
        "volume_ratio": 1.2,
        "distance_support_20d": 0.08,
        "distance_support_60d": 0.12,
        "distance_support_120d": 0.15,
        "distance_sma20": 0.07,
        "distance_sma50": 0.12,
        "distance_sma200": 0.20,
        "sector_relative_strength_20d": 0.08,
        "close_location": 0.85,
        "macd_histogram_change": 0.01,
        "macd_histogram": 0.03,
        "intraday_score": 80,
    }
    score, reversal = score_technical(row)
    assert reversal <= 0.05
    assert score < 35


def test_analyst_revisions_are_not_double_counted_when_missing():
    row = {"analyst_consensus_score": 80, "analyst_target_upside": 0.30, "analyst_count": 10, "analyst_bullish_changes_30d": 2, "analyst_bearish_changes_30d": 0}
    score = score_analysts(row)
    assert 0 <= score <= 100
    assert score < 100


def test_setup_classification_is_not_always_quality_value():
    assert _classify_setup(80, 55, 45, 0.70, {}) == "high-beta mean reversion"
    assert _classify_setup(55, 80, 70, 0.40, {}) == "quality/value pullback"
    assert _classify_setup(55, 80, 40, 0.40, {}) == "structural growth"
