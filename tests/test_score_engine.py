import pandas as pd

from score_engine import calculate_score


def test_four_component_score_weights():
    row = pd.Series({
        "trader_similarity_score": 80,
        "technical_score": 70,
        "fundamental_score": 60,
        "analyst_score": 50,
    })
    result = calculate_score(row)
    assert result["overall_score"] == 68.5
    assert result["signal"] == "WATCH"


def test_four_component_score_exposes_all_components():
    row = pd.Series({
        "trader_similarity_score": 90,
        "technical_score": 80,
        "fundamental_score": 70,
        "analyst_score": 60,
    })
    result = calculate_score(row)
    assert result["trader_score"] == 90
    assert result["technical_score"] == 80
    assert result["fundamental_score"] == 70
    assert result["analyst_score"] == 60
    assert result["overall_score"] == 78.5
