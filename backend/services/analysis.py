"""Analysis orchestration service.

Attaches forecast weather to route checkpoints, classifies risk levels per checkpoint
with load escalation rules, and summarizes route-level mileage risk statistics.
Source of truth: ARCHITECTURE.md section 3, RULES.md section A, ASSUMPTIONS.md, and Phase3.md.
"""

import copy
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from django.core.cache import cache

from risk.config import FORECAST_FUTURE_DAYS, RiskLevel
from risk.recommend import rank_routes
from risk.rules import classify_checkpoint
from risk.scoring import summarize_route
from services.checkpoints import build_checkpoints, choose_interval
from services.geometry import simplify_geometry
from services.open_meteo import (
    compute_weather_window,
    fetch_cells_weather,
    snap_to_grid,
    weather_at,
)
from services.osrm import NoRouteError, fetch_routes


def attach_weather(
    routes: List[Dict[str, Any]],
    load_lbs: Optional[float] = None,
    departure_time: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """Attach forecast weather, classify risk, and summarize route statistics.

    Args:
        routes: List of route dictionaries containing 'checkpoints' and 'distance_mi'.
        load_lbs: Cargo weight in pounds for load-rule escalation.
        departure_time: Departure time (ISO 8601 string or datetime).

    Returns:
        Dict with 'routes' (augmented in-place with weather and risk) and 'warnings'.
    """
    if not routes:
        return {"routes": [], "warnings": []}

    # 1. Collect all checkpoints and deduplicate 0.1 degree grid cells
    cells_set = set()
    eta_datetimes = []
    for rt in routes:
        for cp in rt.get("checkpoints", []):
            lat = cp.get("lat")
            lon = cp.get("lon")
            if lat is not None and lon is not None:
                cells_set.add(snap_to_grid(lat, lon))
            eta_val = cp.get("eta")
            if eta_val:
                if isinstance(eta_val, str):
                    dt = datetime.fromisoformat(eta_val.replace("Z", "+00:00"))
                elif isinstance(eta_val, datetime):
                    dt = eta_val
                else:
                    dt = datetime.fromtimestamp(float(eta_val), tz=timezone.utc)
                eta_datetimes.append(dt)

    unique_cells = list(cells_set)

    # 2. Determine explicit forecast window (departure rounded down to last ETA/48h + margin)
    if departure_time:
        if isinstance(departure_time, str):
            dep_utc = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
        elif isinstance(departure_time, datetime):
            dep_utc = departure_time
        else:
            dep_utc = datetime.fromtimestamp(float(departure_time), tz=timezone.utc)
    elif eta_datetimes:
        dep_utc = min(eta_datetimes)
    else:
        dep_utc = datetime.now(timezone.utc)

    last_eta = max(eta_datetimes) if eta_datetimes else None
    start_utc, end_utc = compute_weather_window(dep_utc, last_eta)

    # 3. Fetch weather once for all unique grid cells in explicit window
    weather_map, warnings = fetch_cells_weather(
        unique_cells, start_utc=start_utc, end_utc=end_utc
    )

    unknown_checkpoints_found = False

    # 3. Attach weather and classify each checkpoint across all routes
    for rt in routes:
        checkpoints = rt.get("checkpoints", [])
        for cp in checkpoints:
            lat = cp.get("lat")
            lon = cp.get("lon")
            eta = cp.get("eta")

            cell = snap_to_grid(lat, lon) if lat is not None and lon is not None else None
            cell_data = weather_map.get(cell) if cell else None

            w = weather_at(cell_data, eta) if eta else {
                "wind_mph": None,
                "gust_mph": None,
                "rain_in_hr": None,
                "snow_in_hr": None,
            }

            cp["wind_mph"] = w["wind_mph"]
            cp["gust_mph"] = w["gust_mph"]
            cp["rain_in_hr"] = w["rain_in_hr"]
            cp["snow_in_hr"] = w["snow_in_hr"]

            level, drivers = classify_checkpoint(
                wind_mph=w["wind_mph"],
                rain_in_hr=w["rain_in_hr"],
                snow_in_hr=w["snow_in_hr"],
                load_lbs=load_lbs,
            )

            cp["level"] = level.value
            cp["drivers"] = drivers

            if level == RiskLevel.UNKNOWN:
                unknown_checkpoints_found = True

        # 4. Summarize route risk stats (miles_by_level, avg_risk, blocked)
        dist_mi = float(rt.get("distance_mi", 0.0))
        summary = summarize_route(checkpoints, dist_mi)
        rt["miles_by_level"] = summary["miles_by_level"]
        rt["avg_risk"] = summary["avg_risk"]
        rt["blocked"] = summary["blocked"]

    if unknown_checkpoints_found:
        msg = "Some checkpoints could not retrieve weather forecast data and were marked Unknown."
        if msg not in warnings:
            warnings.append(msg)

    return {
        "routes": routes,
        "warnings": warnings,
    }


logger = logging.getLogger("truck_routing.analyze")
ANALYZE_CACHE_TTL_S = 300  # 5 minutes


def run_analyze_pipeline(
    origin: Dict[str, Any],
    destination: Dict[str, Any],
    departure_time_utc: datetime,
    load_lbs: float,
    checkpoint_interval_mi: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute complete routing, checkpointing, weather analysis, and ranking pipeline.

    Args:
        origin: Dict with 'lat', 'lon', 'label'
        destination: Dict with 'lat', 'lon', 'label'
        departure_time_utc: Datetime in UTC
        load_lbs: Commercial cargo weight in pounds
        checkpoint_interval_mi: Optional manual checkpoint spacing override (10, 25, 50)

    Returns:
        Dict adhering strictly to the contract in API.md:
        recommended_route_id, reason, warnings, routes, timings_ms
    """
    t_total_start = time.perf_counter()

    orig_coords = (float(origin["lat"]), float(origin["lon"]))
    dest_coords = (float(destination["lat"]), float(destination["lon"]))

    dep_iso = departure_time_utc.isoformat()
    cache_key = (
        f"analyze:{round(orig_coords[0], 3)}:{round(orig_coords[1], 3)}:"
        f"{round(dest_coords[0], 3)}:{round(dest_coords[1], 3)}:"
        f"{dep_iso}:{load_lbs}:{checkpoint_interval_mi}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        cached_res = copy.deepcopy(cached)
        cached_res["timings_ms"] = {
            "osrm_primary": 0.0,
            "osrm_fallback": 0.0,
            "weather": 0.0,
            "scoring": 0.0,
            "serialization": 0.0,
        }
        logger.info("Analyze request served from result cache (hit in <1ms).")
        return cached_res

    # 1. Fetch routes from OSRM (or 24h OSRM cache)
    routes_data = fetch_routes(orig_coords, dest_coords)
    raw_routes = routes_data.get("routes", [])
    if not raw_routes:
        raise NoRouteError("No drivable route found between origin and destination.")

    all_warnings = list(routes_data.get("warnings", []))
    osrm_primary_ms = float(routes_data.get("osrm_primary_ms", 0.0))
    osrm_fallback_ms = float(routes_data.get("osrm_fallback_ms", 0.0))

    # 2. Build checkpoints for each route
    for rt in raw_routes:
        dist_mi = float(rt["distance_mi"])
        chosen_interval = choose_interval(dist_mi, override=checkpoint_interval_mi)
        cps = build_checkpoints(rt, chosen_interval, departure_time_utc)
        rt["checkpoints"] = cps
        rt["interval_mi"] = chosen_interval

    # 3. Attach weather, classify risk, and summarize miles
    t_weather_start = time.perf_counter()
    weather_res = attach_weather(
        raw_routes, load_lbs=load_lbs, departure_time=departure_time_utc
    )
    weather_ms = round((time.perf_counter() - t_weather_start) * 1000, 1)

    analyzed_routes = weather_res.get("routes", [])
    for w in weather_res.get("warnings", []):
        if w not in all_warnings:
            all_warnings.append(w)

    # 4. Check for checkpoints beyond forecast horizon
    now_utc = datetime.now(timezone.utc)
    max_forecast_time = now_utc + timedelta(days=FORECAST_FUTURE_DAYS)

    beyond_count = 0
    for rt in analyzed_routes:
        for cp in rt.get("checkpoints", []):
            eta_val = cp.get("eta")
            if isinstance(eta_val, str):
                dt = datetime.fromisoformat(eta_val.replace("Z", "+00:00"))
            elif isinstance(eta_val, datetime):
                dt = eta_val
            else:
                dt = None

            if dt and dt > max_forecast_time:
                beyond_count += 1
                cp["level"] = RiskLevel.UNKNOWN.value
                cp["wind_mph"] = None
                cp["gust_mph"] = None
                cp["rain_in_hr"] = None
                cp["snow_in_hr"] = None

    if beyond_count > 0:
        warning_msg = (
            f"{beyond_count} checkpoints are beyond the forecast horizon and are marked Unknown"
        )
        if warning_msg not in all_warnings:
            all_warnings.append(warning_msg)

    # 5. Rank routes with pure recommender
    t_score_start = time.perf_counter()
    ranking = rank_routes(analyzed_routes)
    scoring_ms = round((time.perf_counter() - t_score_start) * 1000, 1)

    recommended_route_id = ranking.get("recommended_route_id")
    reason = ranking.get("reason", "")
    ordered_routes = ranking.get("routes", [])

    # 6. Format and simplify response per API.md
    t_ser_start = time.perf_counter()
    shaped_routes = []
    for rt in ordered_routes:
        simplified_geom = simplify_geometry(rt.get("geometry", []), tolerance_deg=0.0005)
        formatted_cps = []
        for cp in rt.get("checkpoints", []):
            eta_val = cp.get("eta")
            if isinstance(eta_val, datetime):
                eta_iso = eta_val.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif isinstance(eta_val, str):
                eta_iso = eta_val if eta_val.endswith("Z") else eta_val + "Z"
            else:
                eta_iso = str(eta_val)

            w_mph = cp.get("wind_mph")
            g_mph = cp.get("gust_mph")
            r_in = cp.get("rain_in_hr")
            s_in = cp.get("snow_in_hr")

            formatted_cps.append({
                "mile": round(float(cp.get("mile", 0.0)), 1),
                "lat": round(float(cp.get("lat", 0.0)), 5),
                "lon": round(float(cp.get("lon", 0.0)), 5),
                "eta": eta_iso,
                "wind_mph": round(float(w_mph), 2) if w_mph is not None else None,
                "gust_mph": round(float(g_mph), 2) if g_mph is not None else None,
                "rain_in_hr": round(float(r_in), 2) if r_in is not None else None,
                "snow_in_hr": round(float(s_in), 2) if s_in is not None else None,
                "level": str(cp.get("level", RiskLevel.UNKNOWN.value)),
                "drivers": list(cp.get("drivers", [])),
            })

        avg_risk_val = rt.get("avg_risk")
        shaped_routes.append({
            "id": str(rt.get("id")),
            "geometry": simplified_geom,
            "distance_mi": round(float(rt.get("distance_mi", 0.0)), 1),
            "duration_s": int(round(float(rt.get("duration_s", 0.0)))),
            "interval_mi": int(rt.get("interval_mi", 50)),
            "blocked": bool(rt.get("blocked", False)),
            "avg_risk": round(float(avg_risk_val), 2) if avg_risk_val is not None else None,
            "miles_by_level": {
                k: round(float(v), 1) for k, v in rt.get("miles_by_level", {}).items()
            },
            "checkpoints": formatted_cps,
        })

    serialization_ms = round((time.perf_counter() - t_ser_start) * 1000, 1)

    timings_ms = {
        "osrm_primary": osrm_primary_ms,
        "osrm_fallback": osrm_fallback_ms,
        "weather": weather_ms,
        "scoring": scoring_ms,
        "serialization": serialization_ms,
    }

    total_ms = round((time.perf_counter() - t_total_start) * 1000, 1)
    logger.info(
        "Analyze completed in %.1f ms | osrm_primary: %.1f ms | osrm_fallback: %.1f ms | "
        "weather: %.1f ms | scoring: %.1f ms | serialization: %.1f ms",
        total_ms,
        osrm_primary_ms,
        osrm_fallback_ms,
        weather_ms,
        scoring_ms,
        serialization_ms,
    )

    result = {
        "recommended_route_id": recommended_route_id,
        "reason": reason,
        "warnings": all_warnings,
        "routes": shaped_routes,
        "timings_ms": timings_ms,
    }

    cache.set(cache_key, result, timeout=ANALYZE_CACHE_TTL_S)
    return copy.deepcopy(result)
