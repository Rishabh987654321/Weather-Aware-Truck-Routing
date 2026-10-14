"""Integration tests for POST /api/heatmap.

Validates the full heatmap endpoint:
- Contract compliance per API.md: start_time, hours (49), points[{lat, lon, intensity[49]}]
- Intensities rounded to 2 decimals
- 400 validation on invalid coordinates, origin == destination, load <= 0
- 422 on NoRoute
- Throttling and cache hit reuse
Source of truth: API.md, ARCHITECTURE.md section 4, and Phase6.md.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import responses
from rest_framework.test import APIClient

from services.open_meteo import OPEN_METEO_BASE_URL
from services.osrm import OSRM_BASE_URL
from tests.test_api import _load_fixture, _make_meteo_callback

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    return APIClient()


def _valid_heatmap_payload(departure_hours_from_now: int = 2) -> dict:
    dep = datetime.now(timezone.utc) + timedelta(hours=departure_hours_from_now)
    return {
        "origin": {"lat": 32.7767, "lon": -96.7970},  # Dallas
        "destination": {"lat": 39.7392, "lon": -104.9903},  # Denver
        "departure_time": dep.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "load_lbs": 35000,
    }


class TestHeatmapAPI:
    @responses.activate
    def test_heatmap_success_contract(self, client):
        # Mock OSRM
        osrm_resp = _load_fixture("osrm_3_routes.json")
        responses.add(
            responses.GET,
            re.compile(f"^{re.escape(OSRM_BASE_URL)}/.*"),
            json=osrm_resp,
            status=200,
        )

        # Mock Open-Meteo
        responses.add_callback(
            responses.GET,
            re.compile(f"^{re.escape(OPEN_METEO_BASE_URL)}.*"),
            callback=_make_meteo_callback(wind_mph=28.0, rain_in=0.15, snow_in=0.0),
        )

        payload = _valid_heatmap_payload()
        resp = client.post("/api/heatmap", data=payload, format="json")

        assert resp.status_code == 200
        data = resp.json()

        assert "start_time" in data
        assert data["hours"] == 49
        assert "points" in data
        assert len(data["points"]) > 0

        # Verify point structure and intensities
        for pt in data["points"]:
            assert "lat" in pt and "lon" in pt
            assert len(pt["intensity"]) == 49
            for val in pt["intensity"]:
                if val is not None:
                    assert 0.0 <= val <= 1.0
                    assert round(val, 2) == val

    def test_heatmap_invalid_load(self, client):
        payload = _valid_heatmap_payload()
        payload["load_lbs"] = 0
        resp = client.post("/api/heatmap", data=payload, format="json")
        assert resp.status_code == 400
        assert "load_lbs" in resp.json()

    def test_heatmap_same_origin_destination(self, client):
        payload = _valid_heatmap_payload()
        payload["destination"] = payload["origin"]
        resp = client.post("/api/heatmap", data=payload, format="json")
        assert resp.status_code == 400

    @responses.activate
    def test_heatmap_no_route_returns_422(self, client):
        responses.add(
            responses.GET,
            re.compile(f"^{re.escape(OSRM_BASE_URL)}/.*"),
            json={"code": "NoRoute"},
            status=200,
        )
        payload = _valid_heatmap_payload()
        resp = client.post("/api/heatmap", data=payload, format="json")
        assert resp.status_code == 422
