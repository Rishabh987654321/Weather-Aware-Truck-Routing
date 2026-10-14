"""Unit tests for mile attribution and route risk scoring.

Source of truth: RULES.md section A4 and TESTING.md section 2.
"""

from risk.config import RiskLevel
from risk.scoring import calculate_mile_attributions, summarize_route


def test_mile_attribution_sums_to_distance():
    # 4 checkpoints along a 300-mile route
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.LOW},
        {"mile": 100.0, "level": RiskLevel.MODERATE},
        {"mile": 200.0, "level": RiskLevel.HIGH},
        {"mile": 300.0, "level": RiskLevel.LOW},
    ]
    distance_mi = 300.0

    attributions = calculate_mile_attributions(checkpoints, distance_mi)

    # cp0: [0, 50] = 50
    # cp1: [50, 150] = 100
    # cp2: [150, 250] = 100
    # cp3: [250, 300] = 50
    assert attributions == [50.0, 100.0, 100.0, 50.0]
    assert sum(attributions) == distance_mi


def test_first_and_last_checkpoints_own_half_intervals_correctly():
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.LOW},
        {"mile": 20.0, "level": RiskLevel.LOW},
        {"mile": 80.0, "level": RiskLevel.LOW},
        {"mile": 100.0, "level": RiskLevel.LOW},
    ]
    distance_mi = 100.0

    attributions = calculate_mile_attributions(checkpoints, distance_mi)

    # cp0: [0, 10] = 10
    # cp1: [10, 50] = 40
    # cp2: [50, 90] = 40
    # cp3: [90, 100] = 10
    assert attributions[0] == 10.0
    assert attributions[-1] == 10.0
    assert sum(attributions) == distance_mi


def test_hand_computed_weighted_average_risk():
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.LOW},  # score 0, owns 25 mi
        {"mile": 50.0, "level": RiskLevel.HIGH},  # score 2, owns 50 mi
        {"mile": 100.0, "level": RiskLevel.MODERATE},  # score 1, owns 25 mi
    ]
    distance_mi = 100.0

    summary = summarize_route(checkpoints, distance_mi)

    # Hand calculation: (25*0 + 50*2 + 25*1) / 100 = 125 / 100 = 1.25
    assert summary["miles_by_level"]["low"] == 25.0
    assert summary["miles_by_level"]["high"] == 50.0
    assert summary["miles_by_level"]["moderate"] == 25.0
    assert summary["miles_by_level"]["severe"] == 0.0
    assert summary["miles_by_level"]["no_travel"] == 0.0
    assert summary["miles_by_level"]["unknown"] == 0.0

    assert sum(summary["miles_by_level"].values()) == distance_mi
    assert summary["avg_risk"] == 1.25
    assert summary["blocked"] is False


def test_unknown_excluded_from_average_risk():
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.LOW},  # score 0, owns 25 mi
        {"mile": 50.0, "level": RiskLevel.HIGH},  # score 2, owns 50 mi
        {"mile": 100.0, "level": RiskLevel.UNKNOWN},  # excluded, owns 25 mi
    ]
    distance_mi = 100.0

    summary = summarize_route(checkpoints, distance_mi)

    assert summary["miles_by_level"]["unknown"] == 25.0
    assert sum(summary["miles_by_level"].values()) == distance_mi

    # Known miles = 75.0, sum of scores = 25*0 + 50*2 = 100.0
    # avg_risk = 100.0 / 75.0 = 1.3333
    assert summary["avg_risk"] == 1.3333
    assert summary["blocked"] is False


def test_route_blocked_when_no_travel_miles_present():
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.LOW},
        {"mile": 50.0, "level": RiskLevel.NO_TRAVEL},
        {"mile": 100.0, "level": RiskLevel.LOW},
    ]
    summary = summarize_route(checkpoints, 100.0)

    assert summary["miles_by_level"]["no_travel"] == 50.0
    assert summary["blocked"] is True


def test_all_unknown_returns_none_avg_risk():
    checkpoints = [
        {"mile": 0.0, "level": RiskLevel.UNKNOWN},
        {"mile": 50.0, "level": RiskLevel.UNKNOWN},
        {"mile": 100.0, "level": RiskLevel.UNKNOWN},
    ]
    summary = summarize_route(checkpoints, 100.0)
    assert summary["avg_risk"] is None
    assert summary["miles_by_level"]["unknown"] == 100.0
    assert summary["blocked"] is False

