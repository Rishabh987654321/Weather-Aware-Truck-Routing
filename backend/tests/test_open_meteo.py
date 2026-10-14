"""Unit and integration tests for Open-Meteo weather service and weather attachment.

All external HTTP calls are strictly mocked with responses.
Source of truth: ARCHITECTURE.md, RULES.md, ASSUMPTIONS.md, and Phase3.md.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import responses
from django.core.cache import cache

from services.analysis import attach_weather
from services.open_meteo import (
    OPEN_METEO_BASE_URL,
    fetch_cells_weather,
    snap_to_grid,
    weather_at,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(filename: str):
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def clear_django_cache():
    """Ensure a clean cache state before each test."""
    cache.clear()
    yield
    cache.clear()


def test_snap_to_grid_deduplication():
    """Grid snapping rounds to 0.1 degree and dedupes overlapping checkpoints."""
    # (32.7767, -96.797) and (32.81, -96.84) both round to (32.8, -96.8)
    cell1 = snap_to_grid(32.7767, -96.797)
    cell2 = snap_to_grid(32.81, -96.84)

    assert cell1 == (32.8, -96.8)
    assert cell2 == (32.8, -96.8)

    cells = [cell1, cell2, snap_to_grid(33.52, -97.09)]
    unique_cells = set(cells)
    assert len(unique_cells) == 2


def test_compute_weather_window():
    """Verify window computation for short trip, long trip (>48h), and minimum 48h."""
    from datetime import timedelta

    from services.open_meteo import compute_weather_window

    # Case 1: Short trip (2 hours duration) -> bounded by minimum 48h rule
    # Departure: 2026-10-14 11:15 UTC, last ETA: 13:15 UTC
    dep_short = datetime(2026, 10, 14, 11, 15, tzinfo=timezone.utc)
    last_eta_short = datetime(2026, 10, 14, 13, 15, tzinfo=timezone.utc)
    start1, end1 = compute_weather_window(dep_short, last_eta_short)

    assert start1 == datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc)
    # dep + 48h is 2026-10-16 11:15 UTC -> rounded up: 12:00 -> +1h margin: 13:00 UTC
    assert end1 == datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc)
    assert (end1 - start1) == timedelta(hours=50)

    # Case 2: Long trip (60.5 hours duration) -> bounded by last checkpoint ETA
    dep_long = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
    last_eta_long = dep_long + timedelta(hours=60, minutes=30)  # Day 3, 22:30 UTC
    start2, end2 = compute_weather_window(dep_long, last_eta_long)

    assert start2 == datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
    # 22:30 rounded up to 23:00 + 1h margin -> 24:00 (next day 00:00)
    assert end2 == datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
    assert end2 > dep_long + timedelta(hours=48)

    # Case 3: No last ETA provided (defaults to departure + 48h)
    start3, end3 = compute_weather_window(dep_short, None)
    assert start3 == datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc)
    assert end3 == datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc)


def test_cache_key_includes_window():
    """Verify cache key incorporates cell coordinates and start/end hour window."""
    from services.open_meteo import get_cache_key

    cell = (32.8, -96.8)
    start_a = datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc)
    end_a = datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc)

    start_b = datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)
    end_b = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)

    key_a = get_cache_key(cell, start_a, end_a)
    key_b = get_cache_key(cell, start_b, end_b)

    assert key_a == "open_meteo:32.8:-96.8:2026101411:2026101613"
    assert key_b == "open_meteo:32.8:-96.8:2026101506:2026101708"
    assert key_a != key_b


@responses.activate
def test_chunking_splits_when_over_limit(monkeypatch):
    """Chunking splits cell lists over OPEN_METEO_CHUNK_SIZE into multiple parallel requests."""
    monkeypatch.setattr("services.open_meteo.OPEN_METEO_CHUNK_SIZE", 3)

    # 7 distinct cells -> should chunk into [3, 3, 1] -> 3 calls
    cells = [(30.0 + i * 0.1, -95.0) for i in range(7)]

    def request_callback(request):
        # Return mock JSON array matching requested lat count
        lat_param = request.params.get("latitude", "")
        count = len(lat_param.split(","))
        mock_payload = [
            {
                "latitude": 30.0,
                "longitude": -95.0,
                "hourly": {
                    "time": ["2026-10-14T06:00"],
                    "wind_speed_10m": [15.0],
                    "wind_gusts_10m": [20.0],
                    "rain": [0.0],
                    "snowfall": [0.0],
                },
            }
            for _ in range(count)
        ]
        return (200, {}, json.dumps(mock_payload))

    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}"),
        callback=request_callback,
    )

    start_utc = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)

    weather_map, warnings = fetch_cells_weather(cells, start_utc, end_utc)
    assert len(weather_map) == 7
    assert len(responses.calls) == 3
    assert warnings == []


def test_hourly_linear_interpolation_at_half_hour():
    """Hourly linear interpolation at :30 returns the exact midpoint."""
    cell_data = {
        "cell": (32.8, -96.8),
        "timestamps": [
            int(datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc).timestamp()),
        ],
        "wind_speed_10m": [20.0, 30.0],
        "wind_gusts_10m": [25.0, 35.0],
        "rain": [0.10, 0.30],
        "snowfall": [0.0, 1.0],
    }

    # Query at 06:30 UTC
    eta = datetime(2026, 10, 14, 6, 30, tzinfo=timezone.utc)
    w = weather_at(cell_data, eta)

    assert w["wind_mph"] == pytest.approx(25.0)
    assert w["gust_mph"] == pytest.approx(30.0)
    assert w["rain_in_hr"] == pytest.approx(0.20)
    assert w["snow_in_hr"] == pytest.approx(0.50)


def test_eta_outside_window_returns_none_and_becomes_unknown():
    """ETA outside the returned forecast window returns None and becomes Unknown (not low)."""
    from services.open_meteo import compute_weather_window, get_cache_key

    cell_data = {
        "cell": (32.8, -96.8),
        "timestamps": [
            int(datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc).timestamp()),
        ],
        "wind_speed_10m": [10.0, 12.0],
        "wind_gusts_10m": [15.0, 18.0],
        "rain": [0.0, 0.0],
        "snowfall": [0.0, 0.0],
    }

    # Query 2 hours later, outside window
    eta_late = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
    w = weather_at(cell_data, eta_late)
    assert w["wind_mph"] is None
    assert w["rain_in_hr"] is None
    assert w["snow_in_hr"] is None

    routes = [
        {
            "id": "r1",
            "distance_mi": 50.0,
            "checkpoints": [
                {
                    "mile": 50.0,
                    "lat": 32.8,
                    "lon": -96.8,
                    "eta": eta_late.isoformat(),
                }
            ],
        }
    ]

    # Pre-populate cache so no network is called
    dep_time = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
    start_utc, end_utc = compute_weather_window(dep_time, eta_late)
    cache.set(get_cache_key((32.8, -96.8), start_utc, end_utc), cell_data)

    result = attach_weather(routes, load_lbs=30000.0, departure_time=dep_time)
    cp = result["routes"][0]["checkpoints"][0]
    assert cp["level"] == "unknown"
    assert result["routes"][0]["miles_by_level"]["unknown"] == 50.0
    assert result["routes"][0]["avg_risk"] is None


@responses.activate
def test_upstream_timeout_marks_affected_cells_unknown_and_warns():
    """Upstream timeout marks only the affected cells unknown and adds a warning."""
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}"),
        body=requests.Timeout("Connection timed out"),
    )

    routes = [
        {
            "id": "r1",
            "distance_mi": 25.0,
            "checkpoints": [
                {
                    "mile": 25.0,
                    "lat": 32.7767,
                    "lon": -96.797,
                    "eta": "2026-10-14T07:00:00Z",
                }
            ],
        }
    ]

    result = attach_weather(routes, load_lbs=35000.0)
    route = result["routes"][0]
    cp = route["checkpoints"][0]

    assert cp["level"] == "unknown"
    assert route["miles_by_level"]["unknown"] == 25.0
    assert route["avg_risk"] is None
    assert len(result["warnings"]) >= 1
    assert any("Open-Meteo" in w or "Unknown" in w for w in result["warnings"])


@responses.activate
def test_second_identical_call_hits_cache():
    """A second identical call hits the Django cache without making an HTTP request."""
    fixture = _load_fixture("open_meteo_multi_location.json")
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}"),
        json=fixture,
        status=200,
    )

    cells = [(32.8, -96.8), (33.5, -97.1)]
    start_utc = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)

    # First call: makes 1 HTTP request
    weather_map1, warnings1 = fetch_cells_weather(cells, start_utc, end_utc)
    assert len(weather_map1) == 2
    assert len(responses.calls) == 1

    # Second call: served 100% from cache
    weather_map2, warnings2 = fetch_cells_weather(cells, start_utc, end_utc)
    assert len(weather_map2) == 2
    assert len(responses.calls) == 1  # Still 1 call!


@responses.activate
def test_load_changes_level_on_windy_fixture():
    """Load escalation escalates 40 mph wind from High (at 20,000 lb) to Severe (at 42,000 lb)."""
    # Mock a cell where wind is 40.0 mph and rain is 0.0 at 08:00 UTC
    windy_fixture = [
        {
            "latitude": 32.8,
            "longitude": -96.8,
            "hourly": {
                "time": ["2026-10-14T08:00"],
                "wind_speed_10m": [40.0],
                "wind_gusts_10m": [45.0],
                "rain": [0.0],
                "snowfall": [0.0],
            },
        }
    ]

    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}"),
        json=windy_fixture,
        status=200,
    )

    base_route = {
        "id": "r1",
        "distance_mi": 100.0,
        "checkpoints": [
            {
                "mile": 100.0,
                "lat": 32.8,
                "lon": -96.8,
                "eta": "2026-10-14T08:00:00Z",
            }
        ],
    }

    # At 20,000 lb: wind 40 mph is High (score 2)
    import copy

    r_light = copy.deepcopy(base_route)
    res_light = attach_weather([r_light], load_lbs=20000.0)
    cp_light = res_light["routes"][0]["checkpoints"][0]
    assert cp_light["wind_mph"] == 40.0
    assert cp_light["level"] == "high"
    assert res_light["routes"][0]["miles_by_level"]["high"] == 100.0
    assert res_light["routes"][0]["avg_risk"] == 2.0

    # At 42,000 lb: wind 40 mph (>40,000 lb) escalates to Severe (score 3)
    r_heavy = copy.deepcopy(base_route)
    res_heavy = attach_weather([r_heavy], load_lbs=42000.0)
    cp_heavy = res_heavy["routes"][0]["checkpoints"][0]
    assert cp_heavy["wind_mph"] == 40.0
    assert cp_heavy["level"] == "severe"
    assert res_heavy["routes"][0]["miles_by_level"]["severe"] == 100.0
    assert res_heavy["routes"][0]["avg_risk"] == 3.0
