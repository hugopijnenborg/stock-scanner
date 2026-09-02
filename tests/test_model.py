import numpy as np
import pandas as pd

from indicators import add_indicators
from model import technical_opportunity_score


def sample_prices(n=320, trend=0.08):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    x = np.arange(n)
    close = 100 + trend * x + 2 * np.sin(x / 9)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.2,
            "Low": close - 1.2,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        },
        index=idx,
    )


def test_technical_score_is_bounded_and_neutral_is_meaningful():
    prices = sample_prices()
    benchmark = sample_prices(trend=0.05)["Close"]
    features = add_indicators(prices, benchmark)
    features.loc[:, "sector_relative_strength_20d"] = 0.0
    score = technical_opportunity_score(features.iloc[-1])["technical_opportunity_score"]
    assert 0 <= score <= 100
    assert 35 <= score <= 65


def test_market_regime_exists_and_is_bounded():
    prices = sample_prices()
    benchmark = sample_prices(trend=0.05)["Close"]
    features = add_indicators(prices, benchmark)
    regime = features["market_regime_score"].dropna()
    assert not regime.empty
    assert np.isfinite(regime).all()
    assert ((regime >= 0) & (regime <= 1)).all()


def test_sector_strength_is_used():
    prices = sample_prices()
    benchmark = sample_prices(trend=0.05)["Close"]
    features = add_indicators(prices, benchmark)
    base = features.iloc[-1].copy()
    base["sector_relative_strength_20d"] = -0.10
    weak = technical_opportunity_score(base)["technical_opportunity_score"]
    base["sector_relative_strength_20d"] = 0.20
    strong = technical_opportunity_score(base)["technical_opportunity_score"]
    assert strong > weak


def test_stronger_rebound_setup_scores_higher():
    benchmark = sample_prices(trend=0.05)["Close"]
    normal = add_indicators(sample_prices(trend=0.08), benchmark).iloc[-1].copy()
    normal["sector_relative_strength_20d"] = 0.0
    rebound_prices = sample_prices(trend=0.08)
    rebound_prices.iloc[-1, rebound_prices.columns.get_loc("Close")] *= 0.78
    rebound_prices.iloc[-1, rebound_prices.columns.get_loc("Low")] *= 0.77
    rebound = add_indicators(rebound_prices, benchmark).iloc[-1].copy()
    rebound["sector_relative_strength_20d"] = 0.0
    normal_score = technical_opportunity_score(normal)["technical_opportunity_score"]
    rebound_score = technical_opportunity_score(rebound)["technical_opportunity_score"]
    assert rebound_score > normal_score
