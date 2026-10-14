"""Corridor grid generation and weather heatmap service.

Generates a spatial grid along all alternative routes (with lateral offsets),
snaps to 0.1 degree resolution, caps points at 300, and evaluates 49 hourly
continuous risk intensity values (hours 0 to 48 from departure).
Source of truth: ARCHITECTURE.md section 4, API.md (/api/heatmap), and Phase6.md.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from risk.intensity import compute_hourly_intensity
from services.open_meteo import compute_weather_window, fetch_cells_weather, snap_to_grid

# Maximum number of grid points in the corridor to keep payload compact and requests fast
GRID_POINT_CAP: int = 300

# Earth geometry constants
MILES_PER_LAT_DEGREE: float = 69.0
LATERAL_OFFSET_MI: float = 15.0


def _sample_points_from_route(
    route: Dict[str, Any], spacing_mi: float
) -> List[Tuple[float, float, float]]:
    """Sample points along a route with local heading.

    Returns:
        List of (lat, lon, heading_rad) where heading_rad is measured clockwise from North.
    """
    cum_table = route.get("cumulative_table", [])
    if not cum_table:
        # Fallback to coordinates from geometry if cumulative_table missing
        geom = route.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            return []
        # Fallback: estimate simple points
        points = []
        for i in range(len(coords)):
            lon, lat = coords[i][0], coords[i][1]
            if i < len(coords) - 1:
                next_lon, next_lat = coords[i + 1][0], coords[i + 1][1]
                heading = math.atan2(
                    next_lon - lon,
                    (next_lat - lat) * math.cos(math.radians(lat)),
                )
            else:
                heading = points[-1][2] if points else 0.0
            points.append((lat, lon, heading))
        return points

    total_miles = float(route.get("distance_mi", 0.0))
    if total_miles <= 0.0:
        return []

    sampled: List[Tuple[float, float, float]] = []
    target_miles = 0.0
    idx = 0
    num_entries = len(cum_table)

    while target_miles <= total_miles:
        while idx < num_entries - 1 and cum_table[idx]["cum_miles"] < target_miles:
            idx += 1

        curr = cum_table[idx]
        lat = curr["lat"]
        lon = curr["lon"]

        # Calculate local heading from surrounding points
        if idx < num_entries - 1:
            nxt = cum_table[idx + 1]
            dlat = nxt["lat"] - lat
            dlon = (nxt["lon"] - lon) * math.cos(math.radians(lat))
            heading = math.atan2(dlon, dlat)
        elif idx > 0:
            prv = cum_table[idx - 1]
            dlat = lat - prv["lat"]
            dlon = (lon - prv["lon"]) * math.cos(math.radians(lat))
            heading = math.atan2(dlon, dlat)
        else:
            heading = 0.0

        sampled.append((lat, lon, heading))
        target_miles += spacing_mi

    return sampled


def build_corridor_grid(
    routes: List[Dict[str, Any]], cap: int = GRID_POINT_CAP
) -> List[Tuple[float, float]]:
    """Build deduped 0.1 degree grid points along route corridor with lateral offsets.

    Grid points are capped at `cap` (default 300) by adapting spacing on longer trips.
    """
    if not routes:
        return []

    max_dist = max(float(rt.get("distance_mi", 0.0)) for rt in routes)

    # Dynamic spacing: default 22 miles, adjusted upward for very long routes
    # to naturally remain within the grid point cap
    base_spacing = max(22.0, max_dist / 65.0)

    unique_cells = set()

    for rt in routes:
        sampled_pts = _sample_points_from_route(rt, base_spacing)
        for lat, lon, heading in sampled_pts:
            # 1. Center route point
            unique_cells.add(snap_to_grid(lat, lon))

            # 2. Lateral offsets (+/- 15 mi perpendicular to heading)
            cos_lat = math.cos(math.radians(lat))
            miles_per_lon = max(0.1, MILES_PER_LAT_DEGREE * cos_lat)

            # Heading + 90 degrees (right offset)
            right_heading = heading + (math.pi / 2.0)
            dlat_r = (LATERAL_OFFSET_MI * math.cos(right_heading)) / MILES_PER_LAT_DEGREE
            dlon_r = (LATERAL_OFFSET_MI * math.sin(right_heading)) / miles_per_lon
            unique_cells.add(snap_to_grid(lat + dlat_r, lon + dlon_r))

            # Heading - 90 degrees (left offset)
            left_heading = heading - (math.pi / 2.0)
            dlat_l = (LATERAL_OFFSET_MI * math.cos(left_heading)) / MILES_PER_LAT_DEGREE
            dlon_l = (LATERAL_OFFSET_MI * math.sin(left_heading)) / miles_per_lon
            unique_cells.add(snap_to_grid(lat + dlat_l, lon + dlon_l))

    cell_list = sorted(list(unique_cells))

    # Strict cap enforcement: uniform stride downsampling if over cap
    if len(cell_list) > cap:
        step = len(cell_list) / float(cap)
        cell_list = [cell_list[int(i * step)] for i in range(cap)]

    return cell_list


def generate_heatmap_data(
    routes: List[Dict[str, Any]],
    departure_time_utc: datetime,
    load_lbs: float,
) -> Dict[str, Any]:
    """Generate 49-hour corridor weather risk heatmap data.

    Returns payload per API.md:
        {
            "start_time": ISO8601 string,
            "hours": 49,
            "points": [
                {"lat": float, "lon": float, "intensity": [float|null, ...]}
            ]
        }
    """
    dep = (
        departure_time_utc.replace(tzinfo=timezone.utc)
        if departure_time_utc.tzinfo is None
        else departure_time_utc.astimezone(timezone.utc)
    )
    start_utc = dep.replace(minute=0, second=0, microsecond=0)

    # 1. Determine last ETA across all route checkpoints for shared cache window
    eta_datetimes = []
    for rt in routes:
        for cp in rt.get("checkpoints", []):
            eta_val = cp.get("eta")
            if isinstance(eta_val, str):
                eta_datetimes.append(datetime.fromisoformat(eta_val.replace("Z", "+00:00")))
            elif isinstance(eta_val, datetime):
                eta_datetimes.append(eta_val)

    last_eta = max(eta_datetimes) if eta_datetimes else None
    start_window, end_window = compute_weather_window(dep, last_eta)

    # 2. Generate corridor grid points
    grid_cells = build_corridor_grid(routes, cap=GRID_POINT_CAP)

    # 3. Fetch weather for corridor grid cells (reuses cache from analyze)
    weather_map, _ = fetch_cells_weather(
        grid_cells, start_utc=start_window, end_utc=end_window
    )

    # 4. Generate 49 hourly timestamps
    hour_timestamps = [
        int((start_utc + timedelta(hours=h)).timestamp())
        for h in range(49)
    ]

    points = []
    for cell in grid_cells:
        cell_data = weather_map.get(cell)
        intensities: List[Optional[float]] = []

        if not cell_data or "timestamps" not in cell_data:
            intensities = [None] * 49
        else:
            ts_list = cell_data.get("timestamps", [])
            ts_to_idx = {ts: idx for idx, ts in enumerate(ts_list)}

            wind_list = cell_data.get("wind_speed_10m", [])
            rain_list = cell_data.get("rain", [])
            snow_list = cell_data.get("snowfall", [])

            for ts in hour_timestamps:
                idx = ts_to_idx.get(ts)
                if idx is None:
                    intensities.append(None)
                else:
                    w = wind_list[idx] if idx < len(wind_list) else None
                    r = rain_list[idx] if idx < len(rain_list) else None
                    s = snow_list[idx] if idx < len(snow_list) else None

                    val = compute_hourly_intensity(w, r, s, load_lbs)
                    intensities.append(round(val, 2) if val is not None else None)

        points.append({
            "lat": cell[0],
            "lon": cell[1],
            "intensity": intensities,
        })

    return {
        "start_time": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hours": 49,
        "points": points,
    }
