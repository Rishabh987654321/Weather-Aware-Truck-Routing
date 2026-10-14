"""Tests for continuous risk intensity mapping.

Verifies piecewise-linear interpolation, threshold boundary values, monotonicity,
load escalation rules, and missing data handling.
Source of truth: Phase6.md and ARCHITECTURE.md section 4.
"""

import pytest

from risk.intensity import (
    compute_hourly_intensity,
    compute_rain_intensity,
    compute_snow_intensity,
    compute_wind_intensity,
)


class TestPiecewiseWindIntensity:
    def test_wind_threshold_boundaries(self):
        assert compute_wind_intensity(0.0) == pytest.approx(0.0)
        assert compute_wind_intensity(25.0) == pytest.approx(0.25)
        assert compute_wind_intensity(35.0) == pytest.approx(0.50)
        assert compute_wind_intensity(45.0) == pytest.approx(0.75)
        assert compute_wind_intensity(55.0) == pytest.approx(1.00)
        assert compute_wind_intensity(65.0) == pytest.approx(1.00)

    def test_wind_monotonic(self):
        speeds = [0.0, 10.0, 24.9, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 70.0]
        intensities = [compute_wind_intensity(s) for s in speeds]
        for i in range(len(intensities) - 1):
            assert intensities[i] <= intensities[i + 1]


class TestPiecewiseRainIntensity:
    def test_rain_threshold_boundaries(self):
        assert compute_rain_intensity(0.0) == pytest.approx(0.0)
        assert compute_rain_intensity(0.10) == pytest.approx(0.25)
        assert compute_rain_intensity(0.25) == pytest.approx(0.50)
        assert compute_rain_intensity(0.50) == pytest.approx(0.75)
        assert compute_rain_intensity(1.00) == pytest.approx(1.00)
        assert compute_rain_intensity(1.50) == pytest.approx(1.00)

    def test_rain_monotonic(self):
        precips = [0.0, 0.05, 0.10, 0.15, 0.25, 0.35, 0.50, 0.75, 1.00, 2.00]
        intensities = [compute_rain_intensity(p) for p in precips]
        for i in range(len(intensities) - 1):
            assert intensities[i] <= intensities[i + 1]


class TestPiecewiseSnowIntensity:
    def test_snow_threshold_boundaries(self):
        assert compute_snow_intensity(0.0) == pytest.approx(0.0)
        assert compute_snow_intensity(0.5) == pytest.approx(0.25)
        assert compute_snow_intensity(1.0) == pytest.approx(0.50)
        assert compute_snow_intensity(2.0) == pytest.approx(0.75)
        assert compute_snow_intensity(3.0) == pytest.approx(1.00)
        assert compute_snow_intensity(4.0) == pytest.approx(1.00)

    def test_snow_monotonic(self):
        snows = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0]
        intensities = [compute_snow_intensity(s) for s in snows]
        for i in range(len(intensities) - 1):
            assert intensities[i] <= intensities[i + 1]


class TestHourlyIntensityAndLoadEscalation:
    def test_missing_data_returns_none(self):
        assert compute_hourly_intensity(None, None, None, 20_000) is None

    def test_max_across_drivers(self):
        # Wind 30 mph -> 0.375 (Moderate), Rain 0.50 in/hr -> 0.75 (Severe)
        val = compute_hourly_intensity(
            wind_mph=30.0, rain_in_hr=0.50, snow_in_hr=0.0, load_lbs=20_000
        )
        assert val == pytest.approx(0.75)

    def test_load_escalation_rule_3_severe(self):
        # Wind 40 mph is base 0.625 (High).
        # With load 42,000 lb (> 40,000), escalates to at least Severe (0.75).
        normal = compute_hourly_intensity(
            wind_mph=40.0, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=20_000
        )
        escalated = compute_hourly_intensity(
            wind_mph=40.0, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=42_000
        )
        assert normal == pytest.approx(0.625)
        assert escalated == pytest.approx(0.75)

    def test_load_escalation_rule_2_no_travel(self):
        # Wind 50 mph is base 0.875 (Severe).
        # With load 35,000 lb (> 30,000), escalates to No Travel (1.00).
        normal = compute_hourly_intensity(
            wind_mph=50.0, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=25_000
        )
        escalated = compute_hourly_intensity(
            wind_mph=50.0, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=35_000
        )
        assert normal == pytest.approx(0.875)
        assert escalated == pytest.approx(1.00)

    def test_extreme_wind_rule_1_no_travel(self):
        # Wind 60 mph -> 1.0 regardless of load
        val = compute_hourly_intensity(
            wind_mph=60.0, rain_in_hr=0.0, snow_in_hr=0.0, load_lbs=10_000
        )
        assert val == pytest.approx(1.00)
