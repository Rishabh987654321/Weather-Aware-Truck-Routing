"""API Integration tests for POST /api/analyze.

Validates the full pipeline:
- Complete contract compliance per API.md
- 400 validation on coordinates, origin==destination, load, departure window, interval
- 422 on NoRoute
- 502 on OSRM upstream failure
- 200 resilience on weather upstream failure with Unknown checkpoints and warnings
- Null recommendation when all routes are blocked
- Load sensitivity (light vs heavy cargo escalation)
- DRF throttling (429)
All external HTTP requests are strictly mocked with responses.
Source of truth: API.md, ARCHITECTURE.md sections 3 and 7, and Phase4.md.
"""

import copy
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import responses
from rest_framework.test import APIClient

from services.open_meteo import OPEN_METEO_BASE_URL
from services.osrm import OSRM_BASE_URL

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(filename: str):
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_meteo_callback(
    wind_mph: float = 18.0,
    rain_in: float = 0.0,
    snow_in: float = 0.0,
    gust_mph: float = 22.0,
):
    """Generate dynamic mock Open-Meteo response callback handling any batch of coordinates."""

    def callback(request):
        parsed = urllib.parse.urlparse(request.url)
        params = urllib.parse.parse_qs(parsed.query)

        lats_raw = params.get("latitude", [""])[0].split(",")
        lons_raw = params.get("longitude", [""])[0].split(",")

        start_h = params.get("start_hour", ["2026-10-14T06:00"])[0]
        end_h = params.get("end_hour", ["2026-10-16T07:00"])[0]

        start_dt = datetime.fromisoformat(start_h)
        end_dt = datetime.fromisoformat(end_h)

        times = []
        curr = start_dt
        while curr <= end_dt:
            times.append(curr.strftime("%Y-%m-%dT%H:%M"))
            curr += timedelta(hours=1)

        records = []
        for lat_s, lon_s in zip(lats_raw, lons_raw):
            lat = float(lat_s)
            lon = float(lon_s)
            records.append({
                "latitude": lat,
                "longitude": lon,
                "generationtime_ms": 0.1,
                "utc_offset_seconds": 0,
                "timezone": "GMT",
                "timezone_abbreviation": "GMT",
                "elevation": 100.0,
                "hourly_units": {
                    "time": "iso8601",
                    "wind_speed_10m": "mph",
                    "wind_gusts_10m": "mph",
                    "rain": "inch",
                    "snowfall": "inch",
                },
                "hourly": {
                    "time": times,
                    "wind_speed_10m": [wind_mph] * len(times),
                    "wind_gusts_10m": [gust_mph] * len(times),
                    "rain": [rain_in] * len(times),
                    "snowfall": [snow_in] * len(times),
                },
            })

        body = records if len(records) > 1 else records[0]
        return (200, {"Content-Type": "application/json"}, json.dumps(body))

    return callback


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def base_request_payload():
    now_utc = datetime.now(timezone.utc)
    dep_time = (now_utc + timedelta(days=1)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    return {
        "origin": {"lat": 32.7767, "lon": -96.797, "label": "Dallas, TX"},
        "destination": {"lat": 39.7392, "lon": -104.9903, "label": "Denver, CO"},
        "departure_time": dep_time.isoformat(),
        "load_lbs": 42000,
        "checkpoint_interval_mi": None,
    }


@responses.activate
def test_analyze_valid_request_returns_contract(client, base_request_payload):
    """POST /api/analyze returns exact contract from API.md with all fields and types."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=20.0, rain_in=0.0, snow_in=0.0),
    )

    resp = client.post("/api/analyze", base_request_payload, format="json")
    assert resp.status_code == 200

    data = resp.json()
    assert "recommended_route_id" in data
    assert isinstance(data["recommended_route_id"], str)
    assert "reason" in data and isinstance(data["reason"], str)
    assert "warnings" in data and isinstance(data["warnings"], list)
    assert "routes" in data and isinstance(data["routes"], list)
    assert len(data["routes"]) == 3
    assert "timings_ms" in data
    assert "osrm_primary" in data["timings_ms"]
    assert "weather" in data["timings_ms"]

    route = data["routes"][0]
    expected_route_keys = {
        "id",
        "geometry",
        "distance_mi",
        "duration_s",
        "interval_mi",
        "blocked",
        "avg_risk",
        "miles_by_level",
        "checkpoints",
    }
    assert expected_route_keys.issubset(route.keys())
    assert isinstance(route["id"], str)
    assert isinstance(route["geometry"], list)
    assert isinstance(route["distance_mi"], (int, float))
    assert isinstance(route["duration_s"], int)
    assert isinstance(route["interval_mi"], int)
    assert isinstance(route["blocked"], bool)
    assert isinstance(route["avg_risk"], (float, int))

    miles_by_level = route["miles_by_level"]
    for level_key in ("low", "moderate", "high", "severe", "no_travel", "unknown"):
        assert level_key in miles_by_level
        assert isinstance(miles_by_level[level_key], (float, int))

    checkpoints = route["checkpoints"]
    assert len(checkpoints) > 0
    cp = checkpoints[0]
    expected_cp_keys = {
        "mile",
        "lat",
        "lon",
        "eta",
        "wind_mph",
        "gust_mph",
        "rain_in_hr",
        "snow_in_hr",
        "level",
        "drivers",
    }
    assert expected_cp_keys.issubset(cp.keys())
    assert cp["eta"].endswith("Z")
    assert cp["level"] in (
        "low",
        "moderate",
        "high",
        "severe",
        "no_travel",
        "unknown",
    )
    assert isinstance(cp["drivers"], list)


def test_analyze_invalid_coordinates(client, base_request_payload):
    """Latitude > 90 and longitude < -180 return 400 Bad Request."""
    payload_bad_lat = dict(base_request_payload)
    payload_bad_lat["origin"] = {"lat": 95.0, "lon": -96.797}
    r1 = client.post("/api/analyze", payload_bad_lat, format="json")
    assert r1.status_code == 400
    assert "lat" in str(r1.json())

    payload_bad_lon = dict(base_request_payload)
    payload_bad_lon["destination"] = {"lat": 39.7392, "lon": -200.0}
    r2 = client.post("/api/analyze", payload_bad_lon, format="json")
    assert r2.status_code == 400
    assert "lon" in str(r2.json())


def test_analyze_origin_equals_destination(client, base_request_payload):
    """Origin identical to destination returns 400 Bad Request."""
    payload = dict(base_request_payload)
    payload["destination"] = dict(payload["origin"])
    resp = client.post("/api/analyze", payload, format="json")
    assert resp.status_code == 400
    assert "same location" in str(resp.json())


def test_analyze_invalid_load(client, base_request_payload):
    """Cargo load <= 0 returns 400 Bad Request."""
    payload_zero = dict(base_request_payload)
    payload_zero["load_lbs"] = 0
    r1 = client.post("/api/analyze", payload_zero, format="json")
    assert r1.status_code == 400

    payload_neg = dict(base_request_payload)
    payload_neg["load_lbs"] = -5000
    r2 = client.post("/api/analyze", payload_neg, format="json")
    assert r2.status_code == 400


def test_analyze_departure_outside_forecast_window(client, base_request_payload):
    """Departure too far in past or future returns 400 with allowed window message."""
    now_utc = datetime.now(timezone.utc)

    # 30 days in the future
    payload_future = dict(base_request_payload)
    payload_future["departure_time"] = (now_utc + timedelta(days=30)).isoformat()
    r_fut = client.post("/api/analyze", payload_future, format="json")
    assert r_fut.status_code == 400
    assert "outside the allowed forecast window" in str(r_fut.json())

    # 20 days in the past
    payload_past = dict(base_request_payload)
    payload_past["departure_time"] = (now_utc - timedelta(days=20)).isoformat()
    r_past = client.post("/api/analyze", payload_past, format="json")
    assert r_past.status_code == 400
    assert "outside the allowed forecast window" in str(r_past.json())


def test_analyze_invalid_checkpoint_interval(client, base_request_payload):
    """Checkpoint interval not in (10, 25, 50, null) returns 400."""
    payload = dict(base_request_payload)
    payload["checkpoint_interval_mi"] = 15
    resp = client.post("/api/analyze", payload, format="json")
    assert resp.status_code == 400
    assert "checkpoint_interval_mi" in str(resp.json())


@responses.activate
def test_analyze_no_route_returns_422(client, base_request_payload):
    """When OSRM cannot find a drivable route, return 422 Unprocessable Entity."""
    no_route_fixture = _load_fixture("osrm_no_route.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=no_route_fixture,
        status=200,
    )

    resp = client.post("/api/analyze", base_request_payload, format="json")
    assert resp.status_code == 422
    assert "route found" in resp.json().get("error", "").lower()


@responses.activate
def test_analyze_osrm_failure_returns_502(client, base_request_payload):
    """When OSRM service fails with 5xx or connection error, return 502 Bad Gateway."""
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        status=502,
    )

    resp = client.post("/api/analyze", base_request_payload, format="json")
    assert resp.status_code == 502
    assert "service failure" in resp.json().get("error", "")


@responses.activate
def test_analyze_weather_failure_resilience(client, base_request_payload):
    """Weather upstream failures do not fail request: returns 200 with unknown checkpoints."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    # Open-Meteo returns 500 error
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        status=500,
    )

    resp = client.post("/api/analyze", base_request_payload, format="json")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["warnings"]) > 0
    route = data["routes"][0]
    # Checkpoints marked unknown
    assert all(cp["level"] == "unknown" for cp in route["checkpoints"])
    # All checkpoints unknown means avg_risk is null
    assert route["avg_risk"] is None
    assert route["miles_by_level"]["unknown"] > 0


@responses.activate
def test_analyze_all_routes_blocked_null_recommendation(
    client, base_request_payload
):
    """When all routes contain No Travel hazard, recommended_route_id is null."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    # Severe hurricane force wind 65 mph (> 55 mph No Travel)
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=65.0, rain_in=0.0, snow_in=0.0),
    )

    resp = client.post("/api/analyze", base_request_payload, format="json")
    assert resp.status_code == 200

    data = resp.json()
    assert data["recommended_route_id"] is None
    assert "No Travel weather hazards" in data["reason"]
    assert all(r["blocked"] is True for r in data["routes"])
    assert all(r["miles_by_level"]["no_travel"] > 0 for r in data["routes"])


@responses.activate
def test_analyze_load_sensitivity_escalation(client, base_request_payload):
    """Load escalation: 40 mph wind is High risk at 20k lb, escalating to Severe at 42k lb."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    # Wind 40 mph (High without load escalation; Severe with >40k lb load)
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=40.0, rain_in=0.0, snow_in=0.0),
    )

    # Light truck: 20,000 lb
    light_payload = dict(base_request_payload)
    light_payload["load_lbs"] = 20000
    r_light = client.post("/api/analyze", light_payload, format="json")
    assert r_light.status_code == 200
    light_data = r_light.json()
    light_r1 = light_data["routes"][0]
    # At 20,000 lb, 40 mph wind remains High, 0 Severe miles
    assert light_r1["miles_by_level"]["severe"] == 0.0
    assert light_r1["miles_by_level"]["high"] > 0.0

    # Heavy truck: 42,000 lb (clearing cache to rerun with distinct payload key)
    from django.core.cache import cache

    cache.clear()
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    heavy_payload = dict(base_request_payload)
    heavy_payload["load_lbs"] = 42000
    r_heavy = client.post("/api/analyze", heavy_payload, format="json")
    assert r_heavy.status_code == 200
    heavy_data = r_heavy.json()
    heavy_r1 = heavy_data["routes"][0]
    # At 42,000 lb, 40 mph wind escalates to Severe (> 40k lb rule)
    assert heavy_r1["miles_by_level"]["severe"] > 0.0


def test_analyze_throttling(client, monkeypatch):
    """When requests exceed throttle rate, DRF returns 429 Too Many Requests."""
    from api.views import AnalyzeRateThrottle

    # Temporarily set analyze rate to 1/minute for testing
    monkeypatch.setitem(AnalyzeRateThrottle.THROTTLE_RATES, "analyze", "1/minute")

    # First request: fails validation (400) without hitting network, but increments throttle counter
    r1 = client.post("/api/analyze", {}, format="json")
    assert r1.status_code == 400

    # Second request: must be throttled
    resp2 = client.post("/api/analyze", {}, format="json")
    assert resp2.status_code == 429


@responses.activate
def test_cache_same_trip_different_load_makes_zero_osrm_and_zero_weather_calls(
    client, base_request_payload
):
    """Changing only load_lbs reuses both cached OSRM routes and cached weather grid cells."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=20.0, rain_in=0.0, snow_in=0.0),
    )

    # First request with 20,000 lb
    p1 = dict(base_request_payload)
    p1["load_lbs"] = 20000
    r1 = client.post("/api/analyze", p1, format="json")
    assert r1.status_code == 200
    initial_call_count = len(responses.calls)
    assert initial_call_count > 0

    # Second request with 42,000 lb (same origin, dest, departure)
    p2 = dict(base_request_payload)
    p2["load_lbs"] = 42000
    r2 = client.post("/api/analyze", p2, format="json")
    assert r2.status_code == 200

    # Zero new calls made to either OSRM or Open-Meteo!
    assert len(responses.calls) == initial_call_count


@responses.activate
def test_cache_same_trip_shifted_departure_makes_zero_osrm_calls(
    client, base_request_payload
):
    """Shifting departure by 1h re-fetches weather for new window but makes zero OSRM calls."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=20.0, rain_in=0.0, snow_in=0.0),
    )

    # First request
    r1 = client.post("/api/analyze", base_request_payload, format="json")
    assert r1.status_code == 200

    osrm_calls_after_first = sum(
        1 for c in responses.calls if OSRM_BASE_URL in c.request.url
    )
    assert osrm_calls_after_first == 1

    # Second request: departure shifted +1h
    dep_dt = datetime.fromisoformat(base_request_payload["departure_time"])
    p_shifted = dict(base_request_payload)
    p_shifted["departure_time"] = (dep_dt + timedelta(hours=1)).isoformat()

    r2 = client.post("/api/analyze", p_shifted, format="json")
    assert r2.status_code == 200

    # OSRM calls must remain exactly 1 (zero new OSRM calls made!)
    osrm_calls_after_second = sum(
        1 for c in responses.calls if OSRM_BASE_URL in c.request.url
    )
    assert osrm_calls_after_second == 1


@responses.activate
def test_analyze_late_departure_beyond_horizon_warning(client, base_request_payload):
    """Checkpoints beyond forecast horizon get level unknown and a descriptive warning."""
    osrm_fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=15.0, rain_in=0.0, snow_in=0.0),
    )

    # Departure set to 15.8 days in the future
    now_utc = datetime.now(timezone.utc)
    late_dep = now_utc + timedelta(days=15, hours=19)
    payload = dict(base_request_payload)
    payload["departure_time"] = late_dep.isoformat()

    resp = client.post("/api/analyze", payload, format="json")
    assert resp.status_code == 200
    data = resp.json()

    # Must contain warning regarding checkpoints beyond forecast horizon
    assert any("beyond the forecast horizon and are marked Unknown" in w for w in data["warnings"])


@responses.activate
def test_analyze_reverse_direction_does_not_reuse_cache(client, base_request_payload):
    """Dallas to Denver, then Denver to Dallas must NOT reuse cached routes.

    OSRM must be called again, and checkpoint 0 of the second route must be Denver.
    """
    osrm_fixture = _load_fixture("osrm_3_routes.json")

    # Forward: Dallas -> Denver
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=osrm_fixture,
        status=200,
    )

    # Reverse: Denver -> Dallas
    reverse_fixture = copy.deepcopy(osrm_fixture)
    for rt in reverse_fixture["routes"]:
        rt["geometry"]["coordinates"] = list(reversed(rt["geometry"]["coordinates"]))
        for leg in rt["legs"]:
            leg["annotation"]["distance"] = list(reversed(leg["annotation"]["distance"]))
            leg["annotation"]["duration"] = list(reversed(leg["annotation"]["duration"]))

    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-104.9903,39.7392;-96.797,32.7767",
        json=reverse_fixture,
        status=200,
    )

    # Weather callback covers any requested coordinates
    responses.add_callback(
        responses.GET,
        re.compile(rf"^{re.escape(OPEN_METEO_BASE_URL)}\?.*"),
        callback=_make_meteo_callback(wind_mph=15.0, rain_in=0.0, snow_in=0.0),
    )

    # 1. Dallas to Denver
    r1 = client.post("/api/analyze", base_request_payload, format="json")
    assert r1.status_code == 200
    data1 = r1.json()

    # Checkpoint 0 of Dallas to Denver is Dallas
    cp0_r1 = data1["routes"][0]["checkpoints"][0]
    assert cp0_r1["lat"] == pytest.approx(32.7767, abs=0.05)
    assert cp0_r1["lon"] == pytest.approx(-96.797, abs=0.05)

    osrm_calls_after_first = sum(
        1 for c in responses.calls if OSRM_BASE_URL in c.request.url
    )
    assert osrm_calls_after_first == 1

    # 2. Denver to Dallas
    denver_to_dallas_payload = dict(base_request_payload)
    denver_to_dallas_payload["origin"] = {"lat": 39.7392, "lon": -104.9903}
    denver_to_dallas_payload["destination"] = {"lat": 32.7767, "lon": -96.797}

    r2 = client.post("/api/analyze", denver_to_dallas_payload, format="json")
    assert r2.status_code == 200
    data2 = r2.json()

    # OSRM must be called again (not reusing cache from Dallas to Denver)
    osrm_calls_after_second = sum(
        1 for c in responses.calls if OSRM_BASE_URL in c.request.url
    )
    assert osrm_calls_after_second == 2

    # Checkpoint 0 of Denver to Dallas must be Denver
    cp0_r2 = data2["routes"][0]["checkpoints"][0]
    assert cp0_r2["lat"] == pytest.approx(39.7392, abs=0.05)
    assert cp0_r2["lon"] == pytest.approx(-104.9903, abs=0.05)
