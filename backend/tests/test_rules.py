"""Unit tests for risk rules, boundary conditions, and load escalations.

Source of truth: RULES.md section A and TESTING.md section 1.
"""

import pytest

from risk.config import RiskLevel
from risk.rules import (
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
)


@pytest.mark.parametrize(
    "wind_mph, expected",
    [
        (24.9, RiskLevel.LOW),
        (25.0, RiskLevel.MODERATE),
        (34.9, RiskLevel.MODERATE),
        (35.0, RiskLevel.HIGH),
        (44.9, RiskLevel.HIGH),
        (45.0, RiskLevel.SEVERE),
        (54.9, RiskLevel.SEVERE),
        (55.0, RiskLevel.NO_TRAVEL),
    ],
)
def test_wind_boundaries(wind_mph, expected):
    assert classify_wind(wind_mph) == expected


@pytest.mark.parametrize(
    "rain_in_hr, expected",
    [
        (0.099, RiskLevel.LOW),
        (0.10, RiskLevel.MODERATE),
        (0.25, RiskLevel.MODERATE),
        (0.251, RiskLevel.HIGH),
        (0.50, RiskLevel.HIGH),
        (0.501, RiskLevel.SEVERE),
        (1.00, RiskLevel.SEVERE),
        (1.001, RiskLevel.NO_TRAVEL),
    ],
)
def test_rain_boundaries(rain_in_hr, expected):
    assert classify_rain(rain_in_hr) == expected


@pytest.mark.parametrize(
    "snow_in_hr, expected",
    [
        (0.49, RiskLevel.LOW),
        (0.5, RiskLevel.MODERATE),
        (1.0, RiskLevel.MODERATE),
        (1.01, RiskLevel.HIGH),
        (2.0, RiskLevel.HIGH),
        (2.01, RiskLevel.SEVERE),
        (3.0, RiskLevel.SEVERE),
        (3.01, RiskLevel.NO_TRAVEL),
    ],
)
def test_snow_boundaries(snow_in_hr, expected):
    assert classify_snow(snow_in_hr) == expected


@pytest.mark.parametrize(
    "wind_mph, load_lbs, expected",
    [
        (56.0, 1_000.0, RiskLevel.NO_TRAVEL),
        (50.0, 30_001.0, RiskLevel.NO_TRAVEL),
        (50.0, 30_000.0, RiskLevel.SEVERE),
        (40.0, 40_001.0, RiskLevel.SEVERE),
        (40.0, 40_000.0, RiskLevel.HIGH),
        (40.0, 20_000.0, RiskLevel.HIGH),
        (30.0, 50_000.0, RiskLevel.MODERATE),
    ],
)
def test_load_rules(wind_mph, load_lbs, expected):
    level, drivers = classify_checkpoint(
        wind_mph=wind_mph, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=load_lbs
    )
    assert level == expected
    assert len(drivers) > 0


def test_combination_max_across_conditions():
    # wind moderate (28 mph), rain severe (0.80 in/hr), snow low (0.0) -> severe
    level, drivers = classify_checkpoint(
        wind_mph=28.0, rain_in_hr=0.80, snow_in_hr=0.0, load_lbs=20_000.0
    )
    assert level == RiskLevel.SEVERE
    assert any("rain" in d and "Severe" in d for d in drivers)


def test_escalation_never_lowers_level():
    # rain severe (0.70 in/hr) + wind 40 mph + 20,000 lb stays severe
    level, drivers = classify_checkpoint(
        wind_mph=40.0, rain_in_hr=0.70, snow_in_hr=0.0, load_lbs=20_000.0
    )
    assert level == RiskLevel.SEVERE
    assert any("rain" in d and "Severe" in d for d in drivers)


@pytest.mark.parametrize(
    "wind, rain, snow, load",
    [
        (None, 0.0, 0.0, 30_000.0),
        (20.0, None, 0.0, 30_000.0),
        (20.0, 0.0, None, 30_000.0),
        (20.0, 0.0, 0.0, None),
    ],
)
def test_none_inputs_return_unknown(wind, rain, snow, load):
    level, drivers = classify_checkpoint(wind, rain, snow, load)
    assert level == RiskLevel.UNKNOWN
    assert drivers == ["missing weather data -> Unknown"]


def test_known_severe_classified_despite_missing_condition():
    # rain is severe (0.80 in/hr), wind and snow missing -> still classifies as severe
    level, drivers = classify_checkpoint(
        wind_mph=None, rain_in_hr=0.80, snow_in_hr=None, load_lbs=30_000.0
    )
    assert level == RiskLevel.SEVERE
    assert any("rain" in d and "Severe" in d for d in drivers)


def test_known_no_travel_classified_despite_missing_condition():
    # wind >= 55 mph is No Travel regardless of missing rain, snow, or load
    level, drivers = classify_checkpoint(
        wind_mph=56.0, rain_in_hr=None, snow_in_hr=None, load_lbs=None
    )
    assert level == RiskLevel.NO_TRAVEL
    assert any("wind" in d and "No Travel" in d for d in drivers)

