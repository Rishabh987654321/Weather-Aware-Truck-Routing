"""Unit tests for route ranking and recommendation logic.

Source of truth: RULES.md section A5, ASSUMPTIONS.md #8, #9, #17, and TESTING.md section 3.
"""

import random

from risk.recommend import rank_routes


def test_fewest_severe_miles_wins_even_if_slower():
    routes = [
        {
            "id": "Route A",
            "duration_s": 36000,  # 10 hours (slower)
            "miles_by_level": {"severe": 0.0, "high": 20.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.2,
        },
        {
            "id": "Route B",
            "duration_s": 28800,  # 8 hours (faster)
            "miles_by_level": {"severe": 12.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.5,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Route A"
    assert result["reason"] == "No severe weather on this route. Route B has 12 mi."


def test_equal_severe_fewer_high_miles_wins():
    routes = [
        {
            "id": "Route 1",
            "duration_s": 30000,
            "miles_by_level": {"severe": 5.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.1,
        },
        {
            "id": "Route 2",
            "duration_s": 30000,
            "miles_by_level": {"severe": 5.0, "high": 35.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.6,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Route 1"
    assert result["reason"] == "Fewer high-risk weather miles (10 mi vs 35 mi on Route 2)."


def test_equal_severe_high_lower_avg_risk_wins():
    routes = [
        {
            "id": "Route 1",
            "duration_s": 30000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.20,
        },
        {
            "id": "Route 2",
            "duration_s": 30000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.85,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Route 1"
    assert result["reason"] == "Lower weather risk than Route 2."


def test_all_equal_shorter_duration_wins():
    routes = [
        {
            "id": "Route Slow",
            "duration_s": 36000,  # 10 hrs
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.20,
        },
        {
            "id": "Route Fast",
            "duration_s": 32400,  # 9 hrs
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.20,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Route Fast"
    assert result["reason"] == "Weather risk is the same, and this route is faster by 60 min."


def test_route_with_no_travel_loses_to_legal_route():
    routes = [
        {
            "id": "Fast Blocked",
            "duration_s": 20000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 15.0, "unknown": 0.0},
            "avg_risk": 0.1,
        },
        {
            "id": "Safe Legal",
            "duration_s": 35000,
            "miles_by_level": {"severe": 10.0, "high": 50.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.8,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Safe Legal"
    assert "blocked by No Travel weather" in result["reason"]


def test_all_routes_blocked_returns_none_recommendation():
    routes = [
        {
            "id": "Route 1",
            "duration_s": 25000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 10.0, "unknown": 0.0},
            "avg_risk": 2.5,
        },
        {
            "id": "Route 2",
            "duration_s": 26000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 5.0, "unknown": 0.0},
            "avg_risk": 2.2,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] is None
    assert "No Travel weather hazards" in result["reason"]
    assert "later time" in result["reason"]


def test_tie_tolerance_severe_miles():
    # Severe difference is 2 miles (< TIE_MILES = 5), so it falls through to High miles
    routes = [
        {
            "id": "Route Near Tie",
            "duration_s": 30000,
            "miles_by_level": {"severe": 4.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.0,
        },
        {
            "id": "Route Other",
            "duration_s": 30000,
            "miles_by_level": {"severe": 2.0, "high": 30.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.5,
        },
    ]

    result = rank_routes(routes)

    assert result["recommended_route_id"] == "Route Near Tie"
    assert result["reason"] == "Fewer high-risk weather miles (10 mi vs 30 mi on Route Other)."


def test_order_independence_across_permutations():
    routes = [
        {
            "id": "Route Best",
            "duration_s": 25000,
            "miles_by_level": {"severe": 0.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.5,
        },
        {
            "id": "Route Mid",
            "duration_s": 26000,
            "miles_by_level": {"severe": 0.0, "high": 25.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 1.2,
        },
        {
            "id": "Route Worst",
            "duration_s": 27000,
            "miles_by_level": {"severe": 10.0, "high": 20.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 2.0,
        },
    ]

    # Test 50 random permutations
    for _ in range(50):
        shuffled = list(routes)
        random.shuffle(shuffled)
        res = rank_routes(shuffled)
        assert res["recommended_route_id"] == "Route Best"


def test_non_transitive_severe_miles_cascade():
    # Severe miles 0, 4, 8:
    # R0 has 0 severe, 20 high
    # R1 has 4 severe (within 5 mi of min 0), 5 high (fewer high!)
    # R2 has 8 severe (8 - 0 >= 5, eliminated in cascade)
    r0 = {
        "id": "R0",
        "duration_s": 30000,
        "miles_by_level": {"severe": 0.0, "high": 20.0, "no_travel": 0.0, "unknown": 0.0},
        "avg_risk": 1.0,
    }
    r1 = {
        "id": "R1",
        "duration_s": 30000,
        "miles_by_level": {"severe": 4.0, "high": 5.0, "no_travel": 0.0, "unknown": 0.0},
        "avg_risk": 1.0,
    }
    r2 = {
        "id": "R2",
        "duration_s": 20000,
        "miles_by_level": {"severe": 8.0, "high": 0.0, "no_travel": 0.0, "unknown": 0.0},
        "avg_risk": 1.0,
    }

    from itertools import permutations

    for perm in permutations([r0, r1, r2]):
        res = rank_routes(list(perm))
        assert res["recommended_route_id"] == "R1"


def test_high_mile_tie_falls_through_to_avg_risk():
    routes = [
        {
            "id": "Route RiskWinner",
            "duration_s": 30000,
            "miles_by_level": {"severe": 0.0, "high": 12.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.30,
        },
        {
            "id": "Route Other",
            "duration_s": 30000,
            "miles_by_level": {"severe": 0.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.80,
        },
    ]

    res = rank_routes(routes)
    # High miles diff = 2 (< 5), so falls through to avg risk (0.30 vs 0.80)
    assert res["recommended_route_id"] == "Route RiskWinner"
    assert res["reason"] == "Lower weather risk than Route Other."


def test_avg_risk_tie_falls_through_to_duration():
    routes = [
        {
            "id": "Route Faster",
            "duration_s": 28800,  # 8 hours
            "miles_by_level": {"severe": 0.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.42,
        },
        {
            "id": "Route Slower",
            "duration_s": 32400,  # 9 hours
            "miles_by_level": {"severe": 0.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.40,
        },
    ]

    res = rank_routes(routes)
    # Risk diff = 0.02 (< 0.05), so falls through to duration
    assert res["recommended_route_id"] == "Route Faster"
    assert res["reason"] == "Weather risk is about the same, and this route is faster."


def test_all_unknown_route_loses_to_real_data():
    routes = [
        {
            "id": "Route Unknown",
            "duration_s": 25000,
            "miles_by_level": {"severe": 0.0, "high": 0.0, "no_travel": 0.0, "unknown": 100.0},
            "avg_risk": None,
        },
        {
            "id": "Route Real",
            "duration_s": 30000,
            "miles_by_level": {"severe": 0.0, "high": 10.0, "no_travel": 0.0, "unknown": 0.0},
            "avg_risk": 0.50,
        },
    ]

    res = rank_routes(routes)
    assert res["recommended_route_id"] == "Route Real"
    assert res["reason"] == "Route Unknown has less forecast data."
