"""Tests for Nominatim geocoding service and endpoint.

Source of truth: API.md, ARCHITECTURE.md, and TESTING.md section 7.
"""

import json
from pathlib import Path

import pytest
import responses
from django.core.cache import cache
from rest_framework.test import APIClient

from services.geocode import NOMINATIM_URL, search_geocode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(filename: str):
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def clear_django_cache():
    cache.clear()
    yield
    cache.clear()


@responses.activate
def test_geocode_service_parsing_and_caching():
    fixture = _load_fixture("nominatim_dallas.json")
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        json=fixture,
        status=200,
    )

    # First call - hits external mock
    results = search_geocode("Dallas")
    assert len(results) == 1
    assert "Dallas" in results[0]["label"]
    assert results[0]["lat"] == pytest.approx(32.77627, abs=1e-3)
    assert results[0]["lon"] == pytest.approx(-96.79686, abs=1e-3)
    assert len(responses.calls) == 1

    # Second call with same query - served from cache without HTTP request
    results_cached = search_geocode("Dallas")
    assert len(results_cached) == 1
    assert len(responses.calls) == 1  # Still 1 call!


@responses.activate
def test_geocode_endpoint_success():
    fixture = _load_fixture("nominatim_dallas.json")
    responses.add(
        responses.GET,
        NOMINATIM_URL,
        json=fixture,
        status=200,
    )

    client = APIClient()
    response = client.get("/api/geocode?q=Dallas")

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["label"] == "Dallas, Dallas County, Texas, United States"


def test_geocode_endpoint_short_query_returns_400():
    client = APIClient()

    # Missing query
    resp1 = client.get("/api/geocode")
    assert resp1.status_code == 400
    assert "at least 2 characters" in resp1.json().get("error", "")

    # Single character
    resp2 = client.get("/api/geocode?q=a")
    assert resp2.status_code == 400
    assert "at least 2 characters" in resp2.json().get("error", "")
