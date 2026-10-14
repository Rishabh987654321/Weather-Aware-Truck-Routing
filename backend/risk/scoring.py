"""Scoring and mile attribution engine.

Pure Python logic: no Django, no I/O.
Source of truth: RULES.md section A4, ASSUMPTIONS.md #7, and TESTING.md section 2.
"""

from typing import Any, Dict, List, Union

from .config import LEVEL_SCORES, RiskLevel


def calculate_mile_attributions(
    checkpoints: List[Union[Dict[str, Any], Any]], distance_mi: float
) -> List[float]:
    """Calculate the miles attributed to each checkpoint based on neighbor midpoints.

    Each checkpoint owns the half-interval on each side:
    - Checkpoint 0 starts at mile 0.0.
    - Checkpoints 1..N-2 own between neighbor midpoints.
    - Checkpoint N-1 ends at distance_mi.
    Sum of all attributed miles equals distance_mi.
    """
    n = len(checkpoints)
    if n == 0:
        return []
    if n == 1:
        return [float(distance_mi)]

    def _get_mile(cp: Any) -> float:
        if isinstance(cp, dict):
            return float(cp.get("mile", 0.0))
        return float(getattr(cp, "mile", 0.0))

    miles = [_get_mile(cp) for cp in checkpoints]
    attributions: List[float] = []

    for i in range(n):
        # Start bound
        if i == 0:
            start = 0.0
        else:
            start = (miles[i - 1] + miles[i]) / 2.0

        # End bound
        if i == n - 1:
            end = float(distance_mi)
        else:
            end = (miles[i] + miles[i + 1]) / 2.0

        attributions.append(max(0.0, end - start))

    return attributions


def summarize_route(
    checkpoints: List[Union[Dict[str, Any], Any]], distance_mi: float
) -> Dict[str, Any]:
    """Summarize route risk statistics from checkpoints and total distance.

    Returns:
    - miles_by_level: dict of miles for low, moderate, high, severe, no_travel, unknown
    - avg_risk: mile-weighted average score (0..4), excluding unknown
    - blocked: True if no_travel_miles > 0
    """
    distance_mi = float(distance_mi)
    miles_by_level: Dict[str, float] = {
        RiskLevel.LOW.value: 0.0,
        RiskLevel.MODERATE.value: 0.0,
        RiskLevel.HIGH.value: 0.0,
        RiskLevel.SEVERE.value: 0.0,
        RiskLevel.NO_TRAVEL.value: 0.0,
        RiskLevel.UNKNOWN.value: 0.0,
    }

    if not checkpoints or distance_mi <= 0.0:
        return {
            "miles_by_level": miles_by_level,
            "avg_risk": None,
            "blocked": False,
        }

    attributions = calculate_mile_attributions(checkpoints, distance_mi)

    def _get_level(cp: Any) -> str:
        if isinstance(cp, dict):
            val = cp.get("level", RiskLevel.UNKNOWN.value)
        else:
            val = getattr(cp, "level", RiskLevel.UNKNOWN.value)
        if isinstance(val, RiskLevel):
            return val.value
        return str(val).lower()

    for cp, attr_miles in zip(checkpoints, attributions):
        lvl = _get_level(cp)
        if lvl in miles_by_level:
            miles_by_level[lvl] += attr_miles
        else:
            miles_by_level[RiskLevel.UNKNOWN.value] += attr_miles

    # Mile-weighted average risk excluding unknown
    weighted_score_sum = 0.0
    known_miles = 0.0

    for lvl_enum, score in LEVEL_SCORES.items():
        lvl_miles = miles_by_level[lvl_enum.value]
        weighted_score_sum += lvl_miles * score
        known_miles += lvl_miles

    avg_risk = round(weighted_score_sum / known_miles, 4) if known_miles > 0.0 else None

    blocked = miles_by_level[RiskLevel.NO_TRAVEL.value] > 0.0

    return {
        "miles_by_level": miles_by_level,
        "avg_risk": avg_risk,
        "blocked": blocked,
    }
