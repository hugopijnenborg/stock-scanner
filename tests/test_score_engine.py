import pandas as pd
import pytest

from score_engine import (
    ALERT_THRESHOLD,
    FUNDAMENTAL_WEIGHT,
    TECHNICAL_WEIGHT,
    TRADER_WEIGHT,
    WATCH_THRESHOLD,
    calculate_score,
)


def test_weights_are_the_stated_thirty_thirtyfive_thirtyfive():
    assert (TRADER_WEIGHT, TECHNICAL_WEIGHT, FUNDAMENTAL_WEIGHT) == (0.30, 0.35, 0.35)
    assert TRADER_WEIGHT + TECHNICAL_WEIGHT + FUNDAMENTAL_WEIGHT == pytest.approx(1.0)


@pytest.mark.parametrize(
    "trader,technical,fundamental",
    [(80, 70, 60), (90, 80, 70), (10, 90, 50), (100, 100, 100), (0, 0, 0)],
)
def test_score_is_exactly_the_weighted_sum(trader, technical, fundamental):
    """No component may be rescaled before weighting.

    An earlier version relaxed trader and technical but not fundamentals, which
    turned the stated 30/35/35 into an effective 22.8/29.0/48.3 and added a
    fixed +27.5 floor to every score. This asserts the published score can be
    read straight back from the three components.
    """
    row = pd.Series({
        "trader_similarity_score": trader,
        "technical_score": technical,
        "fundamental_score": fundamental,
    })
    expected = 0.30 * trader + 0.35 * technical + 0.35 * fundamental
    result = calculate_score(row)
    assert result["overall_score"] == pytest.approx(expected, abs=0.05)
    assert result["trader_score"] == trader
    assert result["technical_score"] == technical
    assert result["fundamental_score"] == fundamental


def test_components_are_published_unmodified():
    row = pd.Series({
        "trader_similarity_score": 63,
        "technical_score": 49,
        "fundamental_score": 99,
    })
    result = calculate_score(row)
    assert (result["trader_score"], result["technical_score"], result["fundamental_score"]) == (63, 49, 99)
    # 0.30*63 + 0.35*49 + 0.35*99 = 70.7 -- under the honest scale this is a
    # WATCH, not the ALERT the relaxed model produced for the same inputs.
    assert result["overall_score"] == pytest.approx(70.7, abs=0.05)
    assert result["signal"] == "WATCH"


def test_no_hidden_floor_in_the_scale():
    """The relaxed model could never score below 27.5. This one can reach 0."""
    row = pd.Series({
        "trader_similarity_score": 0,
        "technical_score": 0,
        "fundamental_score": 0,
    })
    assert calculate_score(row)["overall_score"] == 0.0


def test_signal_boundaries():
    def signal(value):
        row = pd.Series({
            "trader_similarity_score": value,
            "technical_score": value,
            "fundamental_score": value,
        })
        return calculate_score(row)["signal"]

    assert signal(ALERT_THRESHOLD) == "ALERT"
    assert signal(ALERT_THRESHOLD + 5) == "ALERT"
    assert signal(ALERT_THRESHOLD - 0.5) == "WATCH"
    assert signal(WATCH_THRESHOLD) == "WATCH"
    assert signal(WATCH_THRESHOLD - 0.5) == "NO_SIGNAL"


def test_missing_component_renormalises_the_rest():
    row = pd.Series({
        "trader_similarity_score": 80,
        "technical_score": None,
        "fundamental_score": 60,
    })
    result = calculate_score(row)
    expected = (0.30 * 80 + 0.35 * 60) / (0.30 + 0.35)
    assert result["overall_score"] == pytest.approx(expected, abs=0.05)
    assert result["technical_score"] is None


def test_all_components_missing_is_data_incomplete():
    result = calculate_score(pd.Series({"trader_similarity_score": None}))
    assert result["overall_score"] is None
    assert result["signal"] == "DATA_INCOMPLETE"


def test_every_row_carries_the_model_version():
    row = pd.Series({
        "trader_similarity_score": 50,
        "technical_score": 50,
        "fundamental_score": 50,
    })
    assert calculate_score(row)["model_version"]
