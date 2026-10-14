"""Nominatim geocoding service.

Proxies Nominatim search requests with caching (24 hours TTL), User-Agent
compliance, and response normalization.
Source of truth: ARCHITECTURE.md section 2, API.md, and TESTING.md section 7.
"""

import os
from typing import Any, Dict, List

import requests
from django.core.cache import cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CACHE_TTL_SECONDS = 86400  # 24 hours


def _get_user_agent() -> str:
    """Return User-Agent with contact email per Nominatim policy."""
    contact_email = os.getenv("CONTACT_EMAIL", "haulwise.routing@gmail.com")
    if not contact_email or "@example.com" in contact_email or "@test.com" in contact_email:
        contact_email = "haulwise.routing@gmail.com"
    return f"WeatherAwareTruckRoutingApp/1.0 ({contact_email})"


def search_geocode(query: str) -> List[Dict[str, Any]]:
    """Search locations via Nominatim with 24-hour cache."""
    clean_q = query.strip()
    if len(clean_q) < 2:
        return []

    cache_key = f"geocode:{clean_q.lower()}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    params = {
        "q": clean_q,
        "format": "jsonv2",
        "limit": "5",
        "countrycodes": "us",
    }
    headers = {"User-Agent": _get_user_agent()}

    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        raw_items = resp.json()
    except (requests.RequestException, ValueError):
        return []

    results: List[Dict[str, Any]] = []
    for item in raw_items:
        try:
            results.append(
                {
                    "label": item.get("display_name", ""),
                    "lat": round(float(item["lat"]), 5),
                    "lon": round(float(item["lon"]), 5),
                }
            )
        except (KeyError, ValueError, TypeError):
            continue

    if results:
        cache.set(cache_key, results, timeout=CACHE_TTL_SECONDS)
    return results
