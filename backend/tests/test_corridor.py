"""Tests for corridor grid generation and heatmap data evaluation.

Tests:
- Point sampling along routes
- Lateral offset calculation perpendicular to heading
- Snapping to 0.1 degree grid and deduplication
- Grid point cap enforcement (<= 300 points)
- 49 hourly intensities evaluation
- Handling of missing data (returns None for missing hour)
Source of truth: Phase6.md and ARCHITECTURE.md section 4.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from services.corridor import GRID_POINT_CAP, build_corridor_grid, generate_heatmap_data


def _mock_route(distance_mi: float = 300.0) -> dict:
    # Generates a synthetic route heading north from Dallas
    points = []
    num_pts = int(distance_mi / 5)
    for i in range(num_pts + 1):
        cum = i * 5.0
        points.append({
            "lat": 32.7 + (i * 0.07),
            "lon": -96.8,
            "cum_miles": cum,
            "cum_seconds": cum * 60,
        })
    return {
        "id": "r1",
        "distance_mi": distance_mi,
        "duration_s": distance_mi * 60,
        "cumulative_table": points,
        "checkpoints": [
            {"lat": 32.7, "lon": -96.8, "eta": "2026-10-14T12:00:00Z"},
            {"lat": 35.0, "lon": -96.8, "eta": "2026-10-14T17:00:00Z"},
        ],
    }


class TestCorridorGrid:
    def test_grid_points_snapped_to_one_decimal(self):
        route = _mock_route(100.0)
        grid = build_corridor_grid([route])
        assert len(grid) > 0
        for lat, lon in grid:
            assert round(lat, 1) == lat
            assert round(lon, 1) == lon

    def test_grid_deduplication(self):
        # Two identical routes should yield the exact same deduplicated set of grid cells
        route1 = _mock_route(100.0)
        route2 = _mock_route(100.0)
        grid1 = build_corridor_grid([route1])
        grid_both = build_corridor_grid([route1, route2])
        assert len(grid1) == len(grid_both)

    def test_grid_cap_strictly_enforced(self):
        # Very long route (4,000 miles across country)
        long_route = _mock_route(4000.0)
        grid = build_corridor_grid([long_route], cap=GRID_POINT_CAP)
        assert len(grid) <= GRID_POINT_CAP


class TestHeatmapGeneration:
    @patch("services.corridor.fetch_cells_weather")
    def test_generate_heatmap_payload_structure(self, mock_fetch):
        # Mock weather for each cell with 49 hours
        def fake_fetch(cells, start_utc, end_utc):
            weather_map = {}
            for c in cells:
                weather_map[c] = {
                    "timestamps": [int(start_utc.timestamp()) + (h * 3600) for h in range(49)],
                    "wind_speed_10m": [20.0] * 49,
                    "rain": [0.0] * 49,
                    "snowfall": [0.0] * 49,
                }
            return weather_map, []

        mock_fetch.side_effect = fake_fetch

        route = _mock_route(150.0)
        dep_time = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        result = generate_heatmap_data([route], departure_time_utc=dep_time, load_lbs=35_000)

        assert result["start_time"] == "2026-10-14T12:00:00Z"
        assert result["hours"] == 49
        assert len(result["points"]) > 0

        for pt in result["points"]:
            assert "lat" in pt and "lon" in pt
            assert len(pt["intensity"]) == 49
            for val in pt["intensity"]:
                assert val is not None
                assert 0.0 <= val <= 1.0
                assert round(val, 2) == val

    @patch("services.corridor.fetch_cells_weather")
    def test_generate_heatmap_missing_data_returns_null(self, mock_fetch):
        # Cell data missing from weather fetch
        mock_fetch.return_value = ({}, ["weather warning"])

        route = _mock_route(100.0)
        dep_time = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        result = generate_heatmap_data([route], departure_time_utc=dep_time, load_lbs=35_000)

        assert len(result["points"]) > 0
        for pt in result["points"]:
            # All 49 values should be None (JSON null) when weather is missing
            assert pt["intensity"] == [None] * 49
