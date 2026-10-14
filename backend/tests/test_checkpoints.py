"""Tests for checkpoint builder service.

Source of truth: RULES.md A6, ARCHITECTURE.md, and TESTING.md section 4.
"""

from datetime import datetime, timezone

import pytest

from services.checkpoints import build_checkpoints, choose_interval


@pytest.mark.parametrize(
    "distance_mi, expected_interval",
    [
        (50.0, 10),
        (149.0, 10),
        (150.0, 25),
        (300.0, 25),
        (500.0, 25),
        (501.0, 50),
        (850.0, 50),
    ],
)
def test_choose_interval_boundaries(distance_mi, expected_interval):
    assert choose_interval(distance_mi) == expected_interval


def test_choose_interval_override():
    assert choose_interval(800.0, override=10) == 10
    assert choose_interval(800.0, override=25) == 25
    assert choose_interval(50.0, override=50) == 50

    with pytest.raises(ValueError):
        choose_interval(800.0, override=15)


def test_build_checkpoints_spacing_and_no_duplicate_end():
    # Route of exactly 100 miles with interval 25
    cumulative_table = [
        {"lon": -96.0, "lat": 32.0, "cum_miles": 0.0, "cum_seconds": 0.0},
        {"lon": -98.0, "lat": 34.0, "cum_miles": 50.0, "cum_seconds": 2500.0},
        {"lon": -100.0, "lat": 36.0, "cum_miles": 100.0, "cum_seconds": 5000.0},
    ]
    route = {
        "distance_mi": 100.0,
        "cumulative_table": cumulative_table,
    }
    departure = datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc)

    checkpoints = build_checkpoints(route, interval_mi=25, departure_utc=departure)

    miles = [cp["mile"] for cp in checkpoints]
    assert miles == [0.0, 25.0, 50.0, 75.0, 100.0]
    # No duplicate 100.0 checkpoint
    assert len(miles) == 5


def test_strictly_increasing_miles_and_monotonic_etas():
    cumulative_table = [
        {"lon": -96.0, "lat": 32.0, "cum_miles": 0.0, "cum_seconds": 0.0},
        {"lon": -97.5, "lat": 33.5, "cum_miles": 120.0, "cum_seconds": 6000.0},
        {"lon": -99.0, "lat": 35.0, "cum_miles": 240.0, "cum_seconds": 12000.0},
        {"lon": -100.5, "lat": 36.5, "cum_miles": 310.0, "cum_seconds": 16000.0},
    ]
    route = {
        "distance_mi": 310.0,
        "cumulative_table": cumulative_table,
    }
    departure = datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc)

    checkpoints = build_checkpoints(route, interval_mi=25, departure_utc=departure)

    # Origin and destination always included
    assert checkpoints[0]["mile"] == 0.0
    assert checkpoints[-1]["mile"] == 310.0

    # Strictly increasing miles and monotonic ETAs
    for i in range(len(checkpoints) - 1):
        assert checkpoints[i + 1]["mile"] > checkpoints[i]["mile"]
        assert checkpoints[i + 1]["cumulative_seconds"] >= checkpoints[i]["cumulative_seconds"]
        assert checkpoints[i + 1]["eta_utc"] >= checkpoints[i]["eta_utc"]


def test_interpolation_accuracy():
    # Checkpoint at mile 25 on segment [0, 50] with lat [32.0, 34.0]
    cumulative_table = [
        {"lon": -96.0, "lat": 32.0, "cum_miles": 0.0, "cum_seconds": 0.0},
        {"lon": -98.0, "lat": 34.0, "cum_miles": 50.0, "cum_seconds": 3600.0},
    ]
    route = {
        "distance_mi": 50.0,
        "cumulative_table": cumulative_table,
    }
    departure = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)

    checkpoints = build_checkpoints(route, interval_mi=25, departure_utc=departure)

    cp_mid = checkpoints[1]  # mile 25.0
    assert cp_mid["mile"] == 25.0
    assert cp_mid["lat"] == pytest.approx(33.0, abs=1e-3)
    assert cp_mid["lon"] == pytest.approx(-97.0, abs=1e-3)
    assert cp_mid["cumulative_seconds"] == pytest.approx(1800.0, abs=1e-1)
    assert cp_mid["eta"] == "2026-10-14T12:30:00Z"
