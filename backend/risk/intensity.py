"""Continuous risk intensity mapping for weather heatmap.

Converts wind, rain, and snow weather metrics into a smooth continuous intensity
value in [0.0, 1.0] via piecewise-linear interpolation across the risk thresholds,
with load-rule escalation applied.
Pure Python logic: no Django, no I/O, no network calls.
Source of truth: RULES.md section A, ARCHITECTURE.md section 4, and Phase6.md.
"""

from typing import Optional

from .config import LOAD_THRESHOLD_HEAVY, LOAD_THRESHOLD_VERY_HEAVY


def compute_wind_intensity(mph: Optional[float]) -> Optional[float]:
    """Piecewise-linear intensity for wind speed [0.0, 1.0].

    Thresholds:
    [0, 25) -> [0.0, 0.25)
    [25, 35) -> [0.25, 0.50)
    [35, 45) -> [0.50, 0.75)
    [45, 55) -> [0.75, 1.00)
    >= 55 -> 1.00
    """
    if mph is None:
        return None
    if mph <= 0.0:
        return 0.0
    if mph < 25.0:
        return (mph / 25.0) * 0.25
    if mph < 35.0:
        return 0.25 + ((mph - 25.0) / 10.0) * 0.25
    if mph < 45.0:
        return 0.50 + ((mph - 35.0) / 10.0) * 0.25
    if mph < 55.0:
        return 0.75 + ((mph - 45.0) / 10.0) * 0.25
    return 1.0


def compute_rain_intensity(in_hr: Optional[float]) -> Optional[float]:
    """Piecewise-linear intensity for rain precipitation [0.0, 1.0].

    Thresholds:
    [0.0, 0.10) -> [0.0, 0.25)
    [0.10, 0.25] -> [0.25, 0.50]
    (0.25, 0.50] -> (0.50, 0.75]
    (0.50, 1.00] -> (0.75, 1.00]
    > 1.00 -> 1.00
    """
    if in_hr is None:
        return None
    if in_hr <= 0.0:
        return 0.0
    if in_hr <= 0.10:
        return (in_hr / 0.10) * 0.25
    if in_hr <= 0.25:
        return 0.25 + ((in_hr - 0.10) / 0.15) * 0.25
    if in_hr <= 0.50:
        return 0.50 + ((in_hr - 0.25) / 0.25) * 0.25
    if in_hr <= 1.00:
        return 0.75 + ((in_hr - 0.50) / 0.50) * 0.25
    return 1.0


def compute_snow_intensity(in_hr: Optional[float]) -> Optional[float]:
    """Piecewise-linear intensity for snow precipitation [0.0, 1.0].

    Thresholds:
    [0.0, 0.5) -> [0.0, 0.25)
    [0.5, 1.0] -> [0.25, 0.50]
    (1.0, 2.0] -> (0.50, 0.75]
    (2.0, 3.0] -> (0.75, 1.00]
    > 3.0 -> 1.00
    """
    if in_hr is None:
        return None
    if in_hr <= 0.0:
        return 0.0
    if in_hr <= 0.5:
        return (in_hr / 0.5) * 0.25
    if in_hr <= 1.0:
        return 0.25 + ((in_hr - 0.5) / 0.5) * 0.25
    if in_hr <= 2.0:
        return 0.50 + ((in_hr - 1.0) / 1.0) * 0.25
    if in_hr <= 3.0:
        return 0.75 + ((in_hr - 2.0) / 1.0) * 0.25
    return 1.0


def compute_hourly_intensity(
    wind_mph: Optional[float],
    rain_in_hr: Optional[float],
    snow_in_hr: Optional[float],
    load_lbs: Optional[float],
) -> Optional[float]:
    """Compute continuous weather risk intensity [0.0, 1.0].

    Takes maximum across known weather drivers, then applies load-based
    escalation (raising intensity to at least Severe 0.75 or No Travel 1.00).
    Returns None if all weather data is missing for that hour.
    """
    if wind_mph is None and rain_in_hr is None and snow_in_hr is None:
        return None

    intensities = []
    w_int = compute_wind_intensity(wind_mph)
    if w_int is not None:
        intensities.append(w_int)

    r_int = compute_rain_intensity(rain_in_hr)
    if r_int is not None:
        intensities.append(r_int)

    s_int = compute_snow_intensity(snow_in_hr)
    if s_int is not None:
        intensities.append(s_int)

    if not intensities:
        return None

    base_intensity = max(intensities)
    intensity = base_intensity

    # Apply load escalation rules
    if wind_mph is not None:
        # Rule 1: Wind >= 55 mph -> No Travel (1.0)
        if wind_mph >= 55.0:
            intensity = max(intensity, 1.0)
        # Rule 2: Wind [45, 55) mph and load > 30,000 lb -> No Travel (1.0)
        elif 45.0 <= wind_mph < 55.0 and load_lbs is not None and load_lbs > LOAD_THRESHOLD_HEAVY:
            intensity = max(intensity, 1.0)
        # Rule 3: Wind [35, 45) mph and load > 40,000 lb -> at least Severe (0.75)
        elif (
            35.0 <= wind_mph < 45.0
            and load_lbs is not None
            and load_lbs > LOAD_THRESHOLD_VERY_HEAVY
        ):
            intensity = max(intensity, 0.75)

    return min(1.0, max(0.0, intensity))
