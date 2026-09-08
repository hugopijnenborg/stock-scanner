import numpy as np
import pandas as pd

from opportunity_engine import calculate_opportunity_score, reversal_confirmation, score_technical


def test_opportunity_score_is_bounded():
    components = {k: 50.0 for k in ['technical','fundamentals','valuation','analysts','catalysts','institutional','macro_sector','liquidity_risk']}
    assert calculate_opportunity_score(components, 1.0) == 50.0


def test_opportunity_score_has_data_quality_haircut():
    components = {k: 90.0 for k in ['technical','fundamentals','valuation','analysts','catalysts','institutional','macro_sector','liquidity_risk']}
    full = calculate_opportunity_score(components, 1.0)
    partial = calculate_opportunity_score(components, 0.0)
    assert full == 90.0
    assert partial == 81.0


def test_reversal_confirmation_is_bounded():
    row = {'close_location': 0.9, 'return_1d': 0.05, 'macd_histogram_change': 0.2, 'macd_histogram': -0.1, 'intraday_score': 90}
    value = reversal_confirmation(row)
    assert 0 <= value <= 1


def test_technical_score_is_bounded():
    row = {
        'return_1d': -0.05, 'return_5d': -0.12, 'return_20d': -0.20, 'distance_52w_high': -0.20,
        'rsi_14': 32, 'volume_ratio': 2.0, 'distance_support_20d': 0.02,
        'distance_support_60d': 0.03, 'distance_support_120d': 0.04,
        'distance_sma20': -0.08, 'distance_sma50': -0.10, 'distance_sma200': -0.05,
        'sector_relative_strength_20d': 0.05, 'close_location': 0.8,
        'return_1d': 0.02, 'macd_histogram_change': 0.03, 'macd_histogram': -0.02, 'intraday_score': 80,
    }
    score, reversal = score_technical(row)
    assert 0 <= score <= 100
    assert 0 <= reversal <= 1
