"""Risk rules and checkpoint classification engine.

Pure Python logic: no Django, no I/O, no network calls.
Source of truth: RULES.md section A and TESTING.md section 1.
"""

from typing import List, Optional, Tuple

from .config import (
    LEVEL_DISPLAY,
    LEVEL_SCORES,
    LOAD_THRESHOLD_HEAVY,
    LOAD_THRESHOLD_VERY_HEAVY,
    RiskLevel,
)


def classify_wind(mph: Optional[float]) -> RiskLevel:
    """Classify wind speed in mph.

    Boundary convention: lower-bound inclusive [0,25), [25,35), [35,45), [45,55), [55,inf).
    """
    if mph is None:
        return RiskLevel.UNKNOWN
    if mph < 25.0:
        return RiskLevel.LOW
    if mph < 35.0:
        return RiskLevel.MODERATE
    if mph < 45.0:
        return RiskLevel.HIGH
    if mph < 55.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(in_hr: Optional[float]) -> RiskLevel:
    """Classify rain intensity in inches per hour.

    Boundary convention: upper-bound inclusive
    (<0.10, 0.10<=x<=0.25, 0.25<x<=0.50, 0.50<x<=1.00, >1.00).
    """
    if in_hr is None:
        return RiskLevel.UNKNOWN
    if in_hr < 0.10:
        return RiskLevel.LOW
    if in_hr <= 0.25:
        return RiskLevel.MODERATE
    if in_hr <= 0.50:
        return RiskLevel.HIGH
    if in_hr <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_snow(in_hr: Optional[float]) -> RiskLevel:
    """Classify snow intensity in inches per hour.

    Boundary convention: upper-bound inclusive (<0.5, 0.5<=x<=1.0, 1.0<x<=2.0, 2.0<x<=3.0, >3.0).
    """
    if in_hr is None:
        return RiskLevel.UNKNOWN
    if in_hr < 0.5:
        return RiskLevel.LOW
    if in_hr <= 1.0:
        return RiskLevel.MODERATE
    if in_hr <= 2.0:
        return RiskLevel.HIGH
    if in_hr <= 2.0 + 1.0:  # <= 3.0
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def _format_load(lbs: float) -> str:
    """Format load in lbs with thousands separator."""
    return f"{int(round(lbs)):,}"


def classify_checkpoint(
    wind_mph: Optional[float],
    rain_in_hr: Optional[float],
    snow_in_hr: Optional[float],
    load_lbs: Optional[float],
) -> Tuple[RiskLevel, List[str]]:
    """Determine checkpoint risk level and driving rules.

    1. Classify wind, rain, snow.
    2. Base level is max of the three.
    3. Apply load escalation rules (never lower).
    4. Return (RiskLevel, drivers: List[str]).
    """
    known_conditions = []
    if wind_mph is not None:
        known_conditions.append(
            ("wind", wind_mph, classify_wind(wind_mph), f"wind {wind_mph:.1f} mph")
        )
    if rain_in_hr is not None:
        known_conditions.append(
            ("rain", rain_in_hr, classify_rain(rain_in_hr), f"rain {rain_in_hr:.2f} in/hr")
        )
    if snow_in_hr is not None:
        known_conditions.append(
            ("snow", snow_in_hr, classify_snow(snow_in_hr), f"snow {snow_in_hr:.2f} in/hr")
        )

    if not known_conditions:
        return RiskLevel.UNKNOWN, ["missing weather data -> Unknown"]

    base_score = max(LEVEL_SCORES[c[2]] for c in known_conditions)
    base_level = [lvl for lvl, score in LEVEL_SCORES.items() if score == base_score][0]

    drivers: List[str] = [
        f"{c[3]} -> {LEVEL_DISPLAY[c[2]]}"
        for c in known_conditions
        if LEVEL_SCORES[c[2]] == base_score
    ]

    escalated_level = base_level
    escalation_driver: Optional[str] = None

    # Load escalation rules (escalation only)
    if wind_mph is not None:
        # Rule 1: Wind >= 55 mph -> No Travel (for any load)
        if wind_mph >= 55.0:
            if LEVEL_SCORES[escalated_level] < LEVEL_SCORES[RiskLevel.NO_TRAVEL]:
                escalated_level = RiskLevel.NO_TRAVEL
                escalation_driver = f"wind {wind_mph:.1f} mph -> No Travel"

        # Rule 2: Wind [45, 55) mph and load > 30,000 lb -> No Travel
        elif 45.0 <= wind_mph < 55.0 and load_lbs is not None and load_lbs > LOAD_THRESHOLD_HEAVY:
            if LEVEL_SCORES[escalated_level] < LEVEL_SCORES[RiskLevel.NO_TRAVEL]:
                escalated_level = RiskLevel.NO_TRAVEL
                escalation_driver = (
                    f"wind {wind_mph:.1f} mph + load {_format_load(load_lbs)} lb -> No Travel"
                )

        # Rule 3: Wind [35, 45) mph and load > 40,000 lb -> at least Severe
        elif (
            35.0 <= wind_mph < 45.0
            and load_lbs is not None
            and load_lbs > LOAD_THRESHOLD_VERY_HEAVY
        ):
            if LEVEL_SCORES[escalated_level] < LEVEL_SCORES[RiskLevel.SEVERE]:
                escalated_level = RiskLevel.SEVERE
                escalation_driver = (
                    f"wind {wind_mph:.1f} mph + load {_format_load(load_lbs)} lb -> Severe"
                )

    if escalation_driver is not None:
        drivers = [escalation_driver]

    final_score = LEVEL_SCORES[escalated_level]

    # Return UNKNOWN unless known inputs already reached Severe (3) or higher (4)
    has_missing_inputs = (
        wind_mph is None
        or rain_in_hr is None
        or snow_in_hr is None
        or load_lbs is None
    )
    if has_missing_inputs and final_score < LEVEL_SCORES[RiskLevel.SEVERE]:
        return RiskLevel.UNKNOWN, ["missing weather data -> Unknown"]

    return escalated_level, drivers
