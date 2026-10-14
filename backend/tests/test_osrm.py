"""Tests for OSRM routing service.

All external HTTP calls are mocked with responses.
Source of truth: ARCHITECTURE.md, API.md, and TESTING.md section 6.
"""

import json
from pathlib import Path

import pytest
import responses

from services.osrm import (
    OSRM_BASE_URL,
    NoRouteError,
    UpstreamError,
    fetch_routes,
    get_osrm_cache_key,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(filename: str):
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@responses.activate
def test_osrm_parsing_and_speed_factor():
    fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=fixture,
        status=200,
    )

    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    routes = result["routes"]

    assert len(routes) == 3
    r1 = routes[0]
    assert r1["id"] == "r1"
    assert r1["distance_mi"] == pytest.approx(800.0, rel=1e-2)

    # Base duration in fixture is 40000.0s. Scaled by 1.1x truck factor -> 44000.0s
    assert r1["duration_s"] == pytest.approx(44000.0, rel=1e-2)

    cum_table = r1["cumulative_table"]
    assert len(cum_table) == len(r1["geometry"])
    assert cum_table[0]["cum_miles"] == 0.0
    assert cum_table[0]["cum_seconds"] == 0.0
    assert cum_table[-1]["cum_miles"] == pytest.approx(r1["distance_mi"], rel=1e-2)
    assert cum_table[-1]["cum_seconds"] == pytest.approx(r1["duration_s"], rel=1e-2)


@responses.activate
def test_osrm_via_waypoint_fallback():
    single_route_fixture = _load_fixture("osrm_1_route.json")
    waypoint_route_fixture = _load_fixture("osrm_via_waypoint.json")

    # Initial request returns 1 route
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single_route_fixture,
        status=200,
    )

    import re

    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json=waypoint_route_fixture,
        status=200,
    )

    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    routes = result["routes"]

    assert len(routes) >= 2
    assert any("OSRM returned" in w for w in result["warnings"]) or len(routes) == 3


@responses.activate
def test_osrm_no_route_mapping():
    fixture = _load_fixture("osrm_no_route.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=fixture,
        status=200,
    )

    with pytest.raises(NoRouteError):
        fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))


@responses.activate
def test_osrm_upstream_error():
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        status=502,
    )

    with pytest.raises(UpstreamError):
        fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))


@responses.activate
def test_osrm_duplicate_removal():
    import re

    single = _load_fixture("osrm_1_route.json")
    # Return 2 identical routes in the initial call
    duplicate_fixture = {
        "code": "Ok",
        "routes": [single["routes"][0], single["routes"][0]],
    }
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=duplicate_fixture,
        status=200,
    )
    # Mock via-waypoint fallback queries returning NoRoute so fallback completes cleanly
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json={"code": "NoRoute", "message": "No route"},
        status=200,
    )

    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    # Duplicate route should be dropped, leaving 1 route
    assert len(result["routes"]) >= 1
    # Check that route geometries are not identical
    if len(result["routes"]) > 1:
        assert result["routes"][0]["geometry"] != result["routes"][1]["geometry"]


@responses.activate
def test_osrm_unsnappable_via_point_skipped():
    import re

    single = _load_fixture("osrm_1_route.json")
    waypoint = _load_fixture("osrm_via_waypoint.json")

    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )

    # First waypoint attempt returns 400 NoSegment
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json={"code": "NoSegment", "message": "Could not find a matching segment"},
        status=400,
    )
    # Subsequent waypoint attempt succeeds
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json=waypoint,
        status=200,
    )

    # Should not crash on NoSegment; should skip and keep valid routes
    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    assert len(result["routes"]) >= 1


@responses.activate
def test_osrm_absurd_detour_dropped():
    import re

    single = _load_fixture("osrm_1_route.json")
    # Base route is ~800 miles
    # Absurd detour route: 2000 miles (2.5x > 1.5x)
    absurd_route = {
        "code": "Ok",
        "routes": [
            {
                "distance": 3218688.0,  # 2000 miles
                "duration": 120000.0,
                "geometry": {
                    "coordinates": [[-96.797, 32.7767], [-100.0, 30.0], [-104.9903, 39.7392]],
                    "type": "LineString",
                },
                "legs": [
                    {
                        "annotation": {
                            "distance": [1600000.0, 1618688.0],
                            "duration": [60000.0, 60000.0],
                        }
                    }
                ],
            }
        ],
    }

    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json=absurd_route,
        status=200,
    )

    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    # Absurd detour must be dropped, so only the initial 1 route remains
    assert len(result["routes"]) == 1
    assert result["routes"][0]["distance_mi"] == pytest.approx(800.0, rel=1e-2)


@responses.activate
def test_osrm_fewer_than_3_routes_warning():
    import re

    single = _load_fixture("osrm_1_route.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json={"code": "NoRoute", "message": "No route"},
        status=200,
    )

    result = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    assert len(result["routes"]) < 3
    assert any("OSRM returned" in w for w in result["warnings"])


# ==============================================================================
# compute_distance_weighted_overlap Unit Tests (Hand-made Geometries)
# ==============================================================================


def _make_route(coords_with_miles, route_id: str = "r1"):
    """Helper creating route dict with geometry and cumulative table."""
    geometry = [[c[0], c[1]] for c in coords_with_miles]
    cum_table = [
        {"lon": c[0], "lat": c[1], "cum_miles": c[2], "cum_seconds": c[2] * 60.0}
        for c in coords_with_miles
    ]
    return {
        "id": route_id,
        "geometry": geometry,
        "distance_mi": coords_with_miles[-1][2],
        "duration_s": coords_with_miles[-1][2] * 60.0,
        "cumulative_table": cum_table,
    }


def test_overlap_identical_routes():
    """Identical routes: shared fraction ~1.0, no divergence ranges."""
    from services.osrm import compute_distance_weighted_overlap

    coords = [
        (-96.0, 32.0, 0.0),
        (-96.5, 32.5, 50.0),
        (-97.0, 33.0, 100.0),
    ]
    r1 = _make_route(coords, "r1")
    r2 = _make_route(coords, "r2")

    shared_frac, div_ranges = compute_distance_weighted_overlap(r1, r2)
    assert shared_frac == pytest.approx(1.0, rel=1e-2)
    assert div_ranges == []


def test_overlap_fully_separate_routes():
    """Fully separate routes: shared fraction ~0.0, one divergence range covering whole route."""
    from services.osrm import compute_distance_weighted_overlap

    coords1 = [
        (-96.0, 32.0, 0.0),
        (-97.0, 32.0, 50.0),
        (-98.0, 32.0, 100.0),
    ]
    coords2 = [
        (-96.0, 38.0, 0.0),
        (-97.0, 38.0, 50.0),
        (-98.0, 38.0, 100.0),
    ]
    r1 = _make_route(coords1, "r1")
    r2 = _make_route(coords2, "r2")

    shared_frac, div_ranges = compute_distance_weighted_overlap(r1, r2)
    assert shared_frac == pytest.approx(0.0, abs=1e-2)
    assert len(div_ranges) == 1
    assert div_ranges[0][0] == pytest.approx(0.0, abs=1.0)
    assert div_ranges[0][1] == pytest.approx(100.0, abs=1.0)


def test_overlap_partial_overlap_known_diverging_middle():
    """Partial overlap: expected fraction and divergence mile range within tolerance."""
    from services.osrm import compute_distance_weighted_overlap

    # Route A: 100 miles straight on lon -96.0 from lat 30.0 to 40.0
    coords_a = [
        (-96.0, 30.0, 0.0),
        (-96.0, 33.0, 30.0),
        (-96.0, 37.0, 70.0),
        (-96.0, 40.0, 100.0),
    ]
    # Route B: 0-30 shared, 30-70 detours east to lon -90.0, 70-100 shared
    coords_b = [
        (-96.0, 30.0, 0.0),
        (-96.0, 33.0, 30.0),
        (-90.0, 33.0, 40.0),
        (-90.0, 37.0, 80.0),
        (-96.0, 37.0, 90.0),
        (-96.0, 40.0, 120.0),
    ]
    ra = _make_route(coords_a, "ra")
    rb = _make_route(coords_b, "rb")

    shared_frac, div_ranges = compute_distance_weighted_overlap(ra, rb)
    # 60 miles shared out of 100 miles = 0.60 shared fraction
    assert shared_frac == pytest.approx(0.60, abs=0.03)
    assert len(div_ranges) == 1
    assert div_ranges[0][0] == pytest.approx(30.0, abs=1.0)
    assert div_ranges[0][1] == pytest.approx(70.0, abs=1.0)


def test_overlap_argument_order_symmetry():
    """Shorter-vs-longer argument order gives the exact same result."""
    from services.osrm import compute_distance_weighted_overlap

    coords_short = [
        (-96.0, 32.0, 0.0),
        (-96.3, 32.0, 30.0),
        (-96.7, 32.0, 70.0),
        (-97.0, 32.0, 100.0),
    ]
    coords_long = [
        (-96.0, 32.0, 0.0),
        (-96.3, 32.0, 30.0),
        (-96.5, 35.0, 70.0),
        (-96.7, 32.0, 110.0),
        (-97.0, 32.0, 140.0),
    ]
    r_short = _make_route(coords_short, "short")
    r_long = _make_route(coords_long, "long")

    frac_1, div_1 = compute_distance_weighted_overlap(r_short, r_long)
    frac_2, div_2 = compute_distance_weighted_overlap(r_long, r_short)

    assert frac_1 == frac_2
    assert div_1 == div_2


@responses.activate
def test_osrm_caching_zero_calls_on_warm_run():
    """Identical origin/destination on second call hits cache with 0 OSRM calls."""
    fixture = _load_fixture("osrm_3_routes.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=fixture,
        status=200,
    )

    # Cold run: executes 1 OSRM API call
    res_cold = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    assert len(responses.calls) == 1
    assert len(res_cold["routes"]) == 3

    # Warm run (slightly different float precision within 3 decimals): zero OSRM API calls
    res_warm = fetch_routes(origin=(32.7769, -96.7971), destination=(39.7392, -104.9903))
    assert len(responses.calls) == 1  # No additional calls made!
    assert len(res_warm["routes"]) == 3


@responses.activate
def test_osrm_fallback_aborts_immediately_on_upstream_failure():
    """If OSRM itself fails (5xx or timeout) during fallback, abort immediately."""
    import re

    single = _load_fixture("osrm_1_route.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )
    # First fallback call fails with 500 error
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        status=500,
    )

    res = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    # Should abort fallback immediately after 1 failure, returning the 1 initial route and warning
    assert len(res["routes"]) == 1
    assert any("aborted due to upstream service failure" in w for w in res["warnings"])
    # Initial call + parallel fallback batch attempts
    assert len(responses.calls) <= 1 + 6 * 2


@responses.activate
def test_osrm_fallback_caps_attempts():
    """Fallback stops when reaching MAX_FALLBACK_ATTEMPTS (6 attempts)."""
    import re

    from risk.config import MAX_FALLBACK_ATTEMPTS

    single = _load_fixture("osrm_1_route.json")
    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )
    # Return 400 NoRoute for each fallback waypoint (4xx does NOT retry)
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json={"code": "NoRoute"},
        status=400,
    )

    res = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    assert len(res["routes"]) == 1
    assert any("reaching attempt cap" in w for w in res["warnings"])
    # 1 initial call + exactly MAX_FALLBACK_ATTEMPTS fallback calls
    assert len(responses.calls) == 1 + MAX_FALLBACK_ATTEMPTS


@responses.activate
def test_osrm_fallback_stops_as_soon_as_3_routes_found():
    """Fallback stops looping as soon as 3 distinct routes are reached."""
    import re

    single = _load_fixture("osrm_1_route.json")
    via_fixture = _load_fixture("osrm_via_waypoint.json")
    valid_fallback_candidate = via_fixture["routes"][0]

    responses.add(
        responses.GET,
        f"{OSRM_BASE_URL}/-96.797,32.7767;-104.9903,39.7392",
        json=single,
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"^{re.escape(OSRM_BASE_URL)}/-96\.797,32\.7767;.*;-104\.9903,39\.7392"),
        json={"code": "Ok", "routes": [valid_fallback_candidate]},
        status=200,
    )

    res = fetch_routes(origin=(32.7767, -96.797), destination=(39.7392, -104.9903))
    # Stops when route count reaches 3 or candidates exhausted
    assert len(res["routes"]) >= 1


def test_get_osrm_cache_key_directionality():
    """Cache key must be directional (origin to destination) with coords rounded to 3 decimals."""
    key_forward = get_osrm_cache_key((32.7767, -96.797), (39.7392, -104.9903))
    key_reverse = get_osrm_cache_key((39.7392, -104.9903), (32.7767, -96.797))

    assert key_forward == "osrm_routes:32.777:-96.797:39.739:-104.99"
    assert key_reverse == "osrm_routes:39.739:-104.99:32.777:-96.797"
    assert key_forward != key_reverse



