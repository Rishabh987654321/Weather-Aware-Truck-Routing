"""OSRM routing service.

Fetches alternative routes from the OSRM public API, parses cumulative
distance and time annotations, applies truck duration factor, deduplicates
near-identical geometries using distance-weighted overlap, and safely falls
back to via-waypoints if fewer than 3 routes are returned.
Source of truth: ARCHITECTURE.md section 2-3, RULES.md A5, and TESTING.md section 6.
"""

import copy
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.core.cache import cache

from risk.config import (
    MAX_FALLBACK_ATTEMPTS,
    MAX_FALLBACK_TIME_S,
    OSRM_CACHE_TTL_S,
    TRUCK_SPEED_FACTOR,
)

# Distance conversion constant
METRES_PER_MILE = 1609.344
OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
RETRY_DELAY_S = float(os.getenv("OSRM_RETRY_DELAY", "0.5"))


class NoRouteError(Exception):
    """Raised when OSRM indicates no route exists between points."""

    pass


class UpstreamError(Exception):
    """Raised when OSRM request times out, returns HTTP 5xx, or network fails."""

    pass


def _get_user_agent() -> str:
    """Return user-agent with contact email per OSRM usage policy."""
    contact_email = os.getenv("CONTACT_EMAIL", "truckrouting@example.com")
    return f"WeatherAwareTruckRouting/1.0 ({contact_email})"


def _call_osrm_api(coords_str: str, alternatives: bool = True) -> Dict[str, Any]:
    """Call OSRM API with retry on network failure or 5xx, never on 4xx."""
    url = f"{OSRM_BASE_URL}/{coords_str}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "annotations": "distance,duration",
    }
    if alternatives:
        params["alternatives"] = "3"

    headers = {"User-Agent": _get_user_agent()}

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "NoRoute":
                    raise NoRouteError("No route found between coordinates.")
                if data.get("code") != "Ok":
                    raise UpstreamError(
                        f"OSRM returned error code: {data.get('code')}"
                    )
                return data
            elif 400 <= resp.status_code < 500:
                # 4xx client errors (e.g. NoRoute, NoSegment, 400) - NEVER RETRY
                is_json = resp.headers.get("content-type", "").startswith("application/json")
                data = resp.json() if is_json else {}
                code = data.get("code", "")
                if code in ("NoRoute", "NoSegment", "InvalidValue"):
                    raise NoRouteError(f"No route found between coordinates: {code}")
                raise NoRouteError(f"OSRM client error HTTP {resp.status_code}: {resp.text}")
            elif resp.status_code >= 500:
                # 5xx server error: retry once
                if attempt == 0 and RETRY_DELAY_S > 0:
                    time.sleep(RETRY_DELAY_S)
                    continue
                raise UpstreamError(f"OSRM server error HTTP {resp.status_code}")
            else:
                raise UpstreamError(f"OSRM returned unexpected HTTP {resp.status_code}")
        except NoRouteError:
            raise
        except (requests.RequestException, TimeoutError) as e:
            last_error = e
            if attempt == 0 and RETRY_DELAY_S > 0:
                time.sleep(RETRY_DELAY_S)

    raise UpstreamError(f"OSRM request failed after retry: {last_error}")


def _build_cumulative_table(
    coordinates: List[List[float]], legs: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, float]], float, float]:
    """Build cumulative distance and seconds table along coordinate list.

    Duration seconds are scaled by TRUCK_SPEED_FACTOR (default 1.1x) to
    reflect commercial heavy truck travel times compared to car routing.
    """
    cum_table: List[Dict[str, float]] = []
    total_cum_miles = 0.0
    total_cum_seconds = 0.0

    # Start at origin coordinate (mile 0, second 0)
    if coordinates:
        cum_table.append(
            {
                "lon": coordinates[0][0],
                "lat": coordinates[0][1],
                "cum_miles": 0.0,
                "cum_seconds": 0.0,
            }
        )

    # Flatten segment distances and durations from legs
    seg_distances_m: List[float] = []
    seg_durations_s: List[float] = []
    for leg in legs:
        annotation = leg.get("annotation", {})
        seg_distances_m.extend(annotation.get("distance", []))
        seg_durations_s.extend(annotation.get("duration", []))

    num_segments = min(len(seg_distances_m), len(coordinates) - 1)

    for i in range(num_segments):
        dist_mi = seg_distances_m[i] / METRES_PER_MILE
        # Apply truck speed factor to segment duration
        dur_s = seg_durations_s[i] * TRUCK_SPEED_FACTOR

        total_cum_miles += dist_mi
        total_cum_seconds += dur_s

        coord = coordinates[i + 1]
        cum_table.append(
            {
                "lon": coord[0],
                "lat": coord[1],
                "cum_miles": round(total_cum_miles, 4),
                "cum_seconds": round(total_cum_seconds, 2),
            }
        )

    return cum_table, total_cum_miles, total_cum_seconds


def _parse_raw_route(
    raw_route: Dict[str, Any], route_id: str
) -> Dict[str, Any]:
    """Parse an individual OSRM route object into application structure."""
    geometry = raw_route.get("geometry", {})
    coordinates = geometry.get("coordinates", [])
    legs = raw_route.get("legs", [])

    cum_table, total_miles, total_seconds = _build_cumulative_table(coordinates, legs)

    # If annotations were missing or truncated, fallback to route-level totals
    if total_miles <= 0.0:
        total_miles = raw_route.get("distance", 0.0) / METRES_PER_MILE
    if total_seconds <= 0.0:
        total_seconds = raw_route.get("duration", 0.0) * TRUCK_SPEED_FACTOR

    return {
        "id": route_id,
        "geometry": coordinates,
        "distance_mi": round(total_miles, 2),
        "duration_s": round(total_seconds, 1),
        "cumulative_table": cum_table,
    }


def compute_distance_weighted_overlap(
    route_a: Dict[str, Any], route_b: Dict[str, Any]
) -> Tuple[float, List[Tuple[float, float]]]:
    """Calculate distance-weighted shared fraction of two routes.

    Always evaluates the shorter route against the longer route so that
    results are order-independent (shorter-vs-longer or longer-vs-shorter).

    Returns:
        (shared_fraction, divergent_mile_ranges)
        where shared_fraction is the fraction (0.0 to 1.0) of shorter route's miles that lie
        within 0.03 degrees (~1.8-2 miles) of other route, and divergent_mile_ranges is a
        list of (start_mile, end_mile) intervals along shorter route where it diverges.
    """
    if route_a.get("distance_mi", 0.0) <= route_b.get("distance_mi", 0.0):
        target_route, other_route = route_a, route_b
    else:
        target_route, other_route = route_b, route_a

    total_dist = float(target_route.get("distance_mi", 0.0))
    geom_b = other_route.get("geometry", [])
    cum_table_a = target_route.get("cumulative_table", [])

    if total_dist <= 0.0 or not geom_b or not cum_table_a:
        return 1.0, []

    tolerance_deg = 0.03
    tolerance_deg_sq = tolerance_deg * tolerance_deg

    def _min_dist_sq_to_b(px: float, py: float) -> float:
        min_sq = float("inf")
        if len(geom_b) <= 200:
            for j in range(len(geom_b) - 1):
                x1, y1 = geom_b[j]
                x2, y2 = geom_b[j + 1]
                dx = x2 - x1
                dy = y2 - y1
                seg_sq = dx * dx + dy * dy
                if seg_sq <= 1e-12:
                    dist_sq = (px - x1) ** 2 + (py - y1) ** 2
                else:
                    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_sq))
                    dist_sq = (px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2
                if dist_sq < min_sq:
                    min_sq = dist_sq
                    if min_sq <= tolerance_deg_sq:
                        return min_sq
            return min_sq

        stride = max(1, len(geom_b) // 100)
        best_idx = 0
        best_v_sq = float("inf")
        for idx in range(0, len(geom_b), stride):
            bx, by = geom_b[idx]
            d_sq = (px - bx) ** 2 + (py - by) ** 2
            if d_sq < best_v_sq:
                best_v_sq = d_sq
                best_idx = idx

        start_j = max(0, best_idx - 3 * stride)
        end_j = min(len(geom_b) - 1, best_idx + 3 * stride)
        for j in range(start_j, end_j):
            x1, y1 = geom_b[j]
            x2, y2 = geom_b[j + 1]
            dx = x2 - x1
            dy = y2 - y1
            seg_sq = dx * dx + dy * dy
            if seg_sq <= 1e-12:
                dist_sq = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_sq))
                dist_sq = (px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2
            if dist_sq < min_sq:
                min_sq = dist_sq
                if min_sq <= tolerance_deg_sq:
                    return min_sq
        return min_sq

    # Sample shorter route at 150 points along cumulative distance
    num_samples = 150
    step_mi = total_dist / num_samples

    shared_miles = 0.0
    divergent_ranges: List[Tuple[float, float]] = []
    current_div_start: Optional[float] = None

    table_idx = 0
    for s in range(num_samples):
        target_m = (s + 0.5) * step_mi
        while (
            table_idx < len(cum_table_a) - 2
            and cum_table_a[table_idx + 1]["cum_miles"] < target_m
        ):
            table_idx += 1

        p1 = cum_table_a[table_idx]
        p2 = cum_table_a[table_idx + 1]
        m1 = p1["cum_miles"]
        m2 = p2["cum_miles"]
        seg_len = m2 - m1
        t = (target_m - m1) / seg_len if seg_len > 1e-7 else 0.0
        px = p1["lon"] + t * (p2["lon"] - p1["lon"])
        py = p1["lat"] + t * (p2["lat"] - p1["lat"])

        dist_sq = _min_dist_sq_to_b(px, py)
        is_shared = dist_sq <= tolerance_deg_sq

        if is_shared:
            shared_miles += step_mi
            if current_div_start is not None:
                divergent_ranges.append(
                    (round(current_div_start, 1), round(target_m, 1))
                )
                current_div_start = None
        else:
            if current_div_start is None:
                current_div_start = max(0.0, target_m - step_mi / 2)

    if current_div_start is not None:
        divergent_ranges.append((round(current_div_start, 1), round(total_dist, 1)))

    shared_fraction = min(1.0, max(0.0, shared_miles / total_dist))
    return shared_fraction, divergent_ranges


def is_near_duplicate(route_a: Dict[str, Any], route_b: Dict[str, Any]) -> bool:
    """Treat two routes as duplicates if > 90% of shorter route's miles lie within 0.03 deg."""
    shared_fraction, _ = compute_distance_weighted_overlap(route_a, route_b)
    return shared_fraction > 0.90


def _generate_via_waypoints(
    origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float
) -> List[Tuple[float, float]]:
    """Generate via-waypoints along corridor with various perpendicular offsets."""
    dx = dest_lon - origin_lon
    dy = dest_lat - origin_lat
    length = math.sqrt(dx * dx + dy * dy)
    if length <= 1e-6:
        return []

    # Perpendicular unit normal
    nx = -dy / length
    ny = dx / length

    waypoints: List[Tuple[float, float]] = []
    # Test at fractions 0.35, 0.50, 0.65 along route
    fractions = [0.50, 0.35, 0.65]
    # Offsets perpendicular: ±15%, ±25%, ±35%
    offsets = [
        0.15 * length,
        -0.15 * length,
        0.25 * length,
        -0.25 * length,
        0.35 * length,
        -0.35 * length,
    ]

    for f in fractions:
        base_lon = origin_lon + f * dx
        base_lat = origin_lat + f * dy
        for off in offsets:
            wp_lon = round(base_lon + off * nx, 5)
            wp_lat = round(base_lat + off * ny, 5)
            waypoints.append((wp_lon, wp_lat))

    return waypoints


def get_osrm_cache_key(origin: Tuple[float, float], destination: Tuple[float, float]) -> str:
    """Return cache key for OSRM routes based on coordinates rounded to 3 decimals."""
    orig_lat, orig_lon = origin
    dest_lat, dest_lon = destination
    return (
        f"osrm_routes:{round(orig_lat, 3)}:{round(orig_lon, 3)}:"
        f"{round(dest_lat, 3)}:{round(dest_lon, 3)}"
    )


def fetch_routes(
    origin: Tuple[float, float],  # (lat, lon)
    destination: Tuple[float, float],  # (lat, lon)
) -> Dict[str, Any]:
    """Fetch up to 3 distinct routes from OSRM with deduplication, safe fallback, and caching.

    Args:
        origin: (lat, lon)
        destination: (lat, lon)

    Returns:
        dict with:
            routes: List of parsed route dicts
            warnings: List of warning strings if fewer than 3 routes could be found
            osrm_primary_ms: Float milliseconds for initial OSRM query (0 if cached)
            osrm_fallback_ms: Float milliseconds for via-waypoint fallback (0 if cached or unneeded)
    """
    cache_key = get_osrm_cache_key(origin, destination)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        cached_copy = copy.deepcopy(cached_result)
        cached_copy["osrm_primary_ms"] = 0.0
        cached_copy["osrm_fallback_ms"] = 0.0
        return cached_copy

    orig_lat, orig_lon = origin
    dest_lat, dest_lon = destination

    coords_str = f"{orig_lon},{orig_lat};{dest_lon},{dest_lat}"

    t_primary_start = time.perf_counter()
    raw_data = _call_osrm_api(coords_str, alternatives=True)
    osrm_primary_ms = round((time.perf_counter() - t_primary_start) * 1000, 1)

    raw_routes = raw_data.get("routes", [])
    if not raw_routes:
        raise NoRouteError("No drivable route found between points.")

    distinct_routes: List[Dict[str, Any]] = []

    for raw_rt in raw_routes:
        candidate = _parse_raw_route(raw_rt, f"r{len(distinct_routes) + 1}")
        if not any(is_near_duplicate(candidate, ex) for ex in distinct_routes):
            distinct_routes.append(candidate)
        if len(distinct_routes) == 3:
            break

    warnings: List[str] = []
    osrm_fallback_ms = 0.0

    # Via-waypoint fallback if fewer than 3 distinct routes returned
    if len(distinct_routes) < 3 and distinct_routes:
        t_fallback_start = time.perf_counter()
        shortest_distance = min(r["distance_mi"] for r in distinct_routes)
        shortest_duration = min(r["duration_s"] for r in distinct_routes)

        waypoints = _generate_via_waypoints(orig_lon, orig_lat, dest_lon, dest_lat)
        selected_waypoints = waypoints[:MAX_FALLBACK_ATTEMPTS]

        def _fetch_waypoint_route(
            wp: Tuple[float, float],
        ) -> Tuple[Tuple[float, float], Optional[Dict[str, Any]], Optional[Exception]]:
            wp_lon, wp_lat = wp
            wp_coords = f"{orig_lon},{orig_lat};{wp_lon},{wp_lat};{dest_lon},{dest_lat}"
            try:
                wp_resp = _call_osrm_api(wp_coords, alternatives=False)
                return (wp, wp_resp, None)
            except Exception as e:
                return (wp, None, e)

        # Run waypoint fallback attempts in parallel with ThreadPoolExecutor
        workers = min(len(selected_waypoints), MAX_FALLBACK_ATTEMPTS)
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_to_wp = {
                executor.submit(_fetch_waypoint_route, wp): wp
                for wp in selected_waypoints
            }
            try:
                for future in as_completed(future_to_wp, timeout=MAX_FALLBACK_TIME_S):
                    if len(distinct_routes) >= 3:
                        for f in future_to_wp:
                            f.cancel()
                        break

                    try:
                        wp, wp_data, exc = future.result()
                    except Exception as err:
                        exc = err
                        wp_data = None

                    if exc is not None:
                        if isinstance(exc, UpstreamError):
                            warnings.append(
                                "OSRM via-waypoint fallback aborted due to upstream "
                                f"service failure: {exc}"
                            )
                            for f in future_to_wp:
                                f.cancel()
                            break
                        # NoRouteError (unsnappable waypoint) -> continue
                        continue

                    if not wp_data:
                        continue

                    wp_routes = wp_data.get("routes", [])
                    if not wp_routes:
                        continue

                    candidate = _parse_raw_route(
                        wp_routes[0], f"r{len(distinct_routes) + 1}"
                    )
                    # Drop fallback route if longer than 1.5x shortest distance or duration
                    if (
                        candidate["distance_mi"] > 1.5 * shortest_distance
                        or candidate["duration_s"] > 1.5 * shortest_duration
                    ):
                        continue

                    # Drop if near-duplicate (>90% shared) with any accepted route
                    if any(is_near_duplicate(candidate, ex) for ex in distinct_routes):
                        continue

                    distinct_routes.append(candidate)
                    if len(distinct_routes) >= 3:
                        for f in future_to_wp:
                            f.cancel()
                        break

            except TimeoutError:
                warnings.append(
                    "OSRM via-waypoint fallback stopped after exceeding time limit "
                    f"({MAX_FALLBACK_TIME_S}s)."
                )

        if len(distinct_routes) < 3 and len(selected_waypoints) >= MAX_FALLBACK_ATTEMPTS:
            warnings.append(
                "OSRM via-waypoint fallback stopped after reaching attempt cap "
                f"({MAX_FALLBACK_ATTEMPTS})."
            )

        osrm_fallback_ms = round((time.perf_counter() - t_fallback_start) * 1000, 1)

    if len(distinct_routes) < 3:
        warnings.append(
            f"OSRM returned {len(distinct_routes)} distinct route(s) "
            "between origin and destination."
        )

    # Re-index route IDs r1, r2, r3
    for idx, rt in enumerate(distinct_routes):
        rt["id"] = f"r{idx + 1}"

    result = {
        "routes": distinct_routes,
        "warnings": warnings,
        "osrm_primary_ms": osrm_primary_ms,
        "osrm_fallback_ms": osrm_fallback_ms,
    }
    cache.set(cache_key, result, timeout=OSRM_CACHE_TTL_S)
    return copy.deepcopy(result)
