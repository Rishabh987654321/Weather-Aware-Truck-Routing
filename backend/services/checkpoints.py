"""Checkpoint builder service.

Determines checkpoint spacing by route distance and places checkpoints along
the route's cumulative distance/time table, calculating precise interpolated
coordinates and monotonic ETAs.
Source of truth: RULES.md A6, ARCHITECTURE.md section 3, and TESTING.md section 4.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

VALID_INTERVALS = {10, 25, 50}


def choose_interval(distance_mi: float, override: Optional[int] = None) -> int:
    """Choose checkpoint spacing interval based on route distance or override.

    Rules:
    - distance < 150 mi: 10 mi
    - 150 <= distance <= 500 mi: 25 mi
    - distance > 500 mi: 50 mi
    - If override is provided, must be one of 10, 25, 50.
    """
    if override is not None:
        if override not in VALID_INTERVALS:
            raise ValueError(
                f"Checkpoint interval override must be one of "
                f"{sorted(VALID_INTERVALS)}, got {override}"
            )
        return int(override)

    distance = float(distance_mi)
    if distance < 150.0:
        return 10
    elif distance <= 500.0:
        return 25
    else:
        return 50


def _interpolate_checkpoint_at_mile(
    cumulative_table: List[Dict[str, float]],
    target_mile: float,
    departure_utc: datetime,
) -> Dict[str, Any]:
    """Linearly interpolate lat, lon, and seconds along cumulative table."""
    if not cumulative_table:
        raise ValueError("Cumulative table cannot be empty.")

    if len(cumulative_table) == 1 or target_mile <= cumulative_table[0]["cum_miles"]:
        entry = cumulative_table[0]
        sec = entry["cum_seconds"]
        eta = departure_utc + timedelta(seconds=sec)
        return {
            "mile": round(target_mile, 1),
            "lat": round(entry["lat"], 5),
            "lon": round(entry["lon"], 5),
            "cumulative_seconds": round(sec, 2),
            "eta": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eta_utc": eta,
        }

    last_entry = cumulative_table[-1]
    if target_mile >= last_entry["cum_miles"]:
        sec = last_entry["cum_seconds"]
        eta = departure_utc + timedelta(seconds=sec)
        return {
            "mile": round(target_mile, 1),
            "lat": round(last_entry["lat"], 5),
            "lon": round(last_entry["lon"], 5),
            "cumulative_seconds": round(sec, 2),
            "eta": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eta_utc": eta,
        }

    # Binary search or scan for segment
    for k in range(len(cumulative_table) - 1):
        p1 = cumulative_table[k]
        p2 = cumulative_table[k + 1]
        m1 = p1["cum_miles"]
        m2 = p2["cum_miles"]

        if m1 <= target_mile <= m2:
            seg_len = m2 - m1
            t = (target_mile - m1) / seg_len if seg_len > 1e-7 else 0.0

            lat = p1["lat"] + t * (p2["lat"] - p1["lat"])
            lon = p1["lon"] + t * (p2["lon"] - p1["lon"])
            sec = p1["cum_seconds"] + t * (p2["cum_seconds"] - p1["cum_seconds"])
            eta = departure_utc + timedelta(seconds=sec)

            return {
                "mile": round(target_mile, 1),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "cumulative_seconds": round(sec, 2),
                "eta": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "eta_utc": eta,
            }

    # Fallback to last entry
    sec = last_entry["cum_seconds"]
    eta = departure_utc + timedelta(seconds=sec)
    return {
        "mile": round(target_mile, 1),
        "lat": round(last_entry["lat"], 5),
        "lon": round(last_entry["lon"], 5),
        "cumulative_seconds": round(sec, 2),
        "eta": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eta_utc": eta,
    }


def build_checkpoints(
    route: Dict[str, Any],
    interval_mi: int,
    departure_utc: datetime,
) -> List[Dict[str, Any]]:
    """Build checkpoint sequence for route.

    Origin and destination are always included. Checkpoint spacing starts at
    mile 0, step by interval_mi, and ends exactly at route distance without
    duplicate end points. Miles strictly increase and ETAs are monotonic.
    """
    if departure_utc.tzinfo is None:
        departure_utc = departure_utc.replace(tzinfo=timezone.utc)
    else:
        departure_utc = departure_utc.astimezone(timezone.utc)

    distance_mi = float(route.get("distance_mi", 0.0))
    cum_table = route.get("cumulative_table", [])

    if not cum_table:
        # Fallback if cumulative table missing
        return []

    # Target mile points
    target_miles: List[float] = [0.0]
    curr_m = float(interval_mi)
    while curr_m < distance_mi:
        target_miles.append(round(curr_m, 1))
        curr_m += interval_mi

    # Ensure destination is included without duplicating if interval lands on end
    if abs(target_miles[-1] - distance_mi) > 0.05:
        target_miles.append(round(distance_mi, 1))

    checkpoints: List[Dict[str, Any]] = []
    for m in target_miles:
        cp = _interpolate_checkpoint_at_mile(cum_table, m, departure_utc)
        checkpoints.append(cp)

    return checkpoints
