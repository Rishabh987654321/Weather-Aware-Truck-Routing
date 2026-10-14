"""Open-Meteo weather service.

Fetches batched hourly forecast data (wind speed, gusts, rain, snowfall),
handles multi-location chunking with thread pool concurrency, snaps to 0.1 degree
grid cells with caching, and provides linear hourly weather interpolation for checkpoint ETAs.
Source of truth: ARCHITECTURE.md sections 2-3, ASSUMPTIONS.md #3, #4, #10, #14, #15,
and Phase3.md.
"""

import bisect
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from django.core.cache import cache

from risk.config import OPEN_METEO_CACHE_TTL_S, OPEN_METEO_CHUNK_SIZE

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
RETRY_DELAY_S = float(os.getenv("OPEN_METEO_RETRY_DELAY", "0.5"))


def _get_user_agent() -> str:
    """Return User-Agent header with contact email per usage policy."""
    contact_email = os.getenv("CONTACT_EMAIL", "truckrouting@example.com")
    return f"WeatherAwareTruckRouting/1.0 ({contact_email})"


def snap_to_grid(lat: float, lon: float) -> Tuple[float, float]:
    """Snap latitude and longitude to a 0.1 degree cell."""
    return round(float(lat), 1), round(float(lon), 1)


def compute_weather_window(
    departure_utc: datetime,
    last_eta_utc: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Compute explicit UTC forecast window for Open-Meteo.

    Window = from departure hour (rounded down, UTC) to the later of
    (last checkpoint ETA, departure + 48 hours) rounded up to next hour, plus 1 hour margin.
    """
    dep = (
        departure_utc.replace(tzinfo=timezone.utc)
        if departure_utc.tzinfo is None
        else departure_utc.astimezone(timezone.utc)
    )

    # 1. Departure hour rounded down
    start_utc = dep.replace(minute=0, second=0, microsecond=0)

    # 2. Later of (last checkpoint ETA, departure + 48 hours)
    min_end = dep + timedelta(hours=48)
    if last_eta_utc is not None:
        last = (
            last_eta_utc.replace(tzinfo=timezone.utc)
            if last_eta_utc.tzinfo is None
            else last_eta_utc.astimezone(timezone.utc)
        )
        target_end = max(last, min_end)
    else:
        target_end = min_end

    # 3. Rounded up to the next hour
    if target_end.minute > 0 or target_end.second > 0 or target_end.microsecond > 0:
        rounded_up = target_end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        rounded_up = target_end.replace(minute=0, second=0, microsecond=0)

    # 4. Plus 1 hour margin
    end_utc = rounded_up + timedelta(hours=1)

    return start_utc, end_utc


def get_cache_key(cell: Tuple[float, float], start_utc: datetime, end_utc: datetime) -> str:
    """Generate cache key including 0.1 degree cell and explicit forecast window."""
    start_str = start_utc.strftime("%Y%m%d%H")
    end_str = end_utc.strftime("%Y%m%d%H")
    return f"open_meteo:{cell[0]:.1f}:{cell[1]:.1f}:{start_str}:{end_str}"


def _call_open_meteo_chunk(
    chunk: List[Tuple[float, float]],
    start_utc: datetime,
    end_utc: datetime,
) -> List[Dict[str, Any]]:
    """Execute a single multi-location Open-Meteo API call for specific window."""
    lats = ",".join(str(c[0]) for c in chunk)
    lons = ",".join(str(c[1]) for c in chunk)

    params: Dict[str, Any] = {
        "latitude": lats,
        "longitude": lons,
        "hourly": "wind_speed_10m,wind_gusts_10m,rain,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "GMT",
        "start_date": start_utc.strftime("%Y-%m-%d"),
        "end_date": end_utc.strftime("%Y-%m-%d"),
        "start_hour": start_utc.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end_utc.strftime("%Y-%m-%dT%H:%M"),
    }
    headers = {"User-Agent": _get_user_agent()}

    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            resp = requests.get(
                OPEN_METEO_BASE_URL,
                params=params,
                headers=headers,
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                else:
                    raise ValueError(f"Unexpected response payload type: {type(data)}")
            else:
                resp.raise_for_status()
        except (requests.RequestException, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt == 0 and RETRY_DELAY_S > 0:
                time.sleep(RETRY_DELAY_S)

    raise RuntimeError(f"Open-Meteo request failed after retry: {last_error}")


def _parse_cell_hourly(
    cell: Tuple[float, float], hourly_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Convert raw hourly response to normalized timestamps and float arrays."""
    time_strs = hourly_data.get("time", [])
    timestamps: List[int] = []
    for t_str in time_strs:
        # Open-Meteo returns 'YYYY-MM-DDTHH:MM' in GMT
        dt = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
        timestamps.append(int(dt.timestamp()))

    return {
        "cell": cell,
        "timestamps": timestamps,
        "wind_speed_10m": hourly_data.get("wind_speed_10m", []),
        "wind_gusts_10m": hourly_data.get("wind_gusts_10m", []),
        "rain": hourly_data.get("rain", []),
        "snowfall": hourly_data.get("snowfall", []),
    }


def fetch_cells_weather(
    cells: List[Tuple[float, float]],
    start_utc: datetime,
    end_utc: datetime,
) -> Tuple[Dict[Tuple[float, float], Optional[Dict[str, Any]]], List[str]]:
    """Fetch forecast weather for grid cells within the specified start_utc to end_utc window.

    Returns:
        (weather_map, warnings)
        where weather_map maps (lat, lon) cell -> parsed cell data (or None if failed).
    """
    unique_cells = sorted(list(set(cells)))

    weather_map: Dict[Tuple[float, float], Optional[Dict[str, Any]]] = {}
    missing_cells: List[Tuple[float, float]] = []

    for cell in unique_cells:
        cache_key = get_cache_key(cell, start_utc, end_utc)
        cached = cache.get(cache_key)
        if cached is not None:
            weather_map[cell] = cached
        else:
            missing_cells.append(cell)

    warnings: List[str] = []
    if not missing_cells:
        return weather_map, warnings

    chunks = [
        missing_cells[i : i + OPEN_METEO_CHUNK_SIZE]
        for i in range(0, len(missing_cells), OPEN_METEO_CHUNK_SIZE)
    ]

    max_workers = min(len(chunks), 4) if chunks else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(_call_open_meteo_chunk, chunk, start_utc, end_utc): chunk
            for chunk in chunks
        }
        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            try:
                raw_list = future.result()
                for cell, raw_obj in zip(chunk, raw_list):
                    hourly = raw_obj.get("hourly", {})
                    cell_data = _parse_cell_hourly(cell, hourly)
                    weather_map[cell] = cell_data
                    cache.set(
                        get_cache_key(cell, start_utc, end_utc),
                        cell_data,
                        timeout=OPEN_METEO_CACHE_TTL_S,
                    )
            except Exception as exc:
                warnings.append(
                    f"Failed to fetch Open-Meteo weather for {len(chunk)} grid cells: {exc}"
                )
                for cell in chunk:
                    weather_map[cell] = None

    return weather_map, warnings


def weather_at(
    cell_data: Optional[Dict[str, Any]],
    eta_utc: Union[str, datetime, int, float],
) -> Dict[str, Optional[float]]:
    """Linearly interpolate hourly forecast data at a specific ETA.

    Returns dict with keys: wind_mph, gust_mph, rain_in_hr, snow_in_hr.
    Returns all None if cell_data is missing or ETA is outside the available time window.
    """
    empty_weather = {
        "wind_mph": None,
        "gust_mph": None,
        "rain_in_hr": None,
        "snow_in_hr": None,
    }
    if not cell_data or not cell_data.get("timestamps"):
        return empty_weather

    # Parse eta_utc to epoch seconds
    if isinstance(eta_utc, str):
        # Support ISO strings like '2026-10-14T07:10:00Z' or '+00:00'
        dt = datetime.fromisoformat(eta_utc.replace("Z", "+00:00"))
        eta_ts = dt.timestamp()
    elif isinstance(eta_utc, datetime):
        dt = eta_utc if eta_utc.tzinfo else eta_utc.replace(tzinfo=timezone.utc)
        eta_ts = dt.timestamp()
    else:
        eta_ts = float(eta_utc)

    timestamps = cell_data["timestamps"]
    if eta_ts < timestamps[0] or eta_ts > timestamps[-1]:
        return empty_weather

    idx = bisect.bisect_right(timestamps, eta_ts)
    if idx == 0:
        i1 = 0
        i2 = 0
        t = 0.0
    elif idx >= len(timestamps):
        i1 = len(timestamps) - 1
        i2 = len(timestamps) - 1
        t = 0.0
    else:
        i1 = idx - 1
        i2 = idx
        span = timestamps[i2] - timestamps[i1]
        t = (eta_ts - timestamps[i1]) / span if span > 0 else 0.0

    def _interpolate_series(series: List[Optional[float]]) -> Optional[float]:
        if not series or i1 >= len(series) or i2 >= len(series):
            return None
        v1 = series[i1]
        v2 = series[i2]
        if v1 is None or v2 is None:
            return None
        val = v1 + t * (v2 - v1)
        return round(float(val), 2)

    return {
        "wind_mph": _interpolate_series(cell_data.get("wind_speed_10m", [])),
        "gust_mph": _interpolate_series(cell_data.get("wind_gusts_10m", [])),
        "rain_in_hr": _interpolate_series(cell_data.get("rain", [])),
        "snow_in_hr": _interpolate_series(cell_data.get("snowfall", [])),
    }
