"""Risk configuration constants and thresholds.

Pure Python configuration without any Django or I/O dependencies.
Source of truth: RULES.md section A, ASSUMPTIONS.md, and Phase1.md.
"""

from enum import Enum
from typing import Dict, List, Tuple


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    NO_TRAVEL = "no_travel"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


# Numeric scores for averaging per RULES.md A1.
# Unknown is excluded from score calculation.
LEVEL_SCORES: Dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MODERATE: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.SEVERE: 3,
    RiskLevel.NO_TRAVEL: 4,
}

# Display labels for human readability
LEVEL_DISPLAY: Dict[RiskLevel, str] = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
    RiskLevel.UNKNOWN: "Unknown",
}

# Threshold tables: (min_inclusive, max_exclusive, level) or (min_exclusive, max_inclusive, level)
# Wind (mph): lower-bound inclusive [0, 25), [25, 35), [35, 45), [45, 55), [55, inf)
WIND_THRESHOLDS: List[Tuple[float, float, RiskLevel]] = [
    (0.0, 25.0, RiskLevel.LOW),
    (25.0, 35.0, RiskLevel.MODERATE),
    (35.0, 45.0, RiskLevel.HIGH),
    (45.0, 55.0, RiskLevel.SEVERE),
    (55.0, float("inf"), RiskLevel.NO_TRAVEL),
]

# Rain (in/hr): upper-bound inclusive (<0.10, 0.10-0.25, 0.25-0.50, 0.50-1.00, >1.00)
# Strictly > 1.00 is No Travel
RAIN_THRESHOLDS: List[Tuple[float, float, RiskLevel]] = [
    (0.0, 0.10, RiskLevel.LOW),
    (0.10, 0.25, RiskLevel.MODERATE),
    (0.25, 0.50, RiskLevel.HIGH),
    (0.50, 1.00, RiskLevel.SEVERE),
    (1.00, float("inf"), RiskLevel.NO_TRAVEL),
]

# Snow (in/hr): upper-bound inclusive (<0.5, 0.5-1.0, 1.0-2.0, 2.0-3.0, >3.0)
# Strictly > 3.0 is No Travel
SNOW_THRESHOLDS: List[Tuple[float, float, RiskLevel]] = [
    (0.0, 0.5, RiskLevel.LOW),
    (0.5, 1.0, RiskLevel.MODERATE),
    (1.0, 2.0, RiskLevel.HIGH),
    (2.0, 3.0, RiskLevel.SEVERE),
    (3.0, float("inf"), RiskLevel.NO_TRAVEL),
]

# Load escalation thresholds (lb)
LOAD_THRESHOLD_HEAVY: float = 30_000.0
LOAD_THRESHOLD_VERY_HEAVY: float = 40_000.0

# Ranking tie tolerances per RULES.md A5
TIE_MILES: float = 5.0
TIE_RISK: float = 0.05

# Spacing table per RULES.md A6: (max_distance_mi_inclusive, interval_mi)
# < 150 mi: 10 mi; 150-500 mi: 25 mi; > 500 mi: 50 mi
SPACING_TABLE: List[Tuple[float, int]] = [
    (150.0, 10),
    (500.0, 25),
    (float("inf"), 50),
]

# Truck vs car routing speed factor (duration multiplier) per ASSUMPTIONS.md #12
TRUCK_SPEED_FACTOR: float = 1.1

# Open-Meteo API config constants per Phase 3
OPEN_METEO_CHUNK_SIZE: int = 20
OPEN_METEO_CACHE_TTL_S: int = 1800

# Forecast horizon limits in days (past and future) per ASSUMPTIONS.md #15
FORECAST_PAST_DAYS: int = 7
FORECAST_FUTURE_DAYS: int = 16

# OSRM routing cache & fallback budget constants per Phase 4
OSRM_CACHE_TTL_S: int = 86400  # 24 hours
MAX_FALLBACK_ATTEMPTS: int = 6
MAX_FALLBACK_TIME_S: float = 8.0

