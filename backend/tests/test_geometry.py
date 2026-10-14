"""Tests for geometry simplification utility.

Source of truth: Phase4.md and ARCHITECTURE.md section 6.
"""

from services.geometry import simplify_geometry


def test_simplify_short_or_empty_coords():
    assert simplify_geometry([]) == []
    assert simplify_geometry([[0.0, 0.0]]) == [[0.0, 0.0]]
    assert simplify_geometry([[0.0, 0.0], [1.0, 1.0]]) == [[0.0, 0.0], [1.0, 1.0]]


def test_simplify_collinear_points():
    # 5 collinear points along a line
    coords = [
        [0.0, 0.0],
        [0.2, 0.2],
        [0.5, 0.5],
        [0.8, 0.8],
        [1.0, 1.0],
    ]
    simplified = simplify_geometry(coords, tolerance_deg=0.0005)
    # Should reduce to just start and end
    assert len(simplified) == 2
    assert simplified == [[0.0, 0.0], [1.0, 1.0]]


def test_simplify_preserves_apex_exceeding_tolerance():
    # Triangle with apex deviating significantly
    coords = [
        [0.0, 0.0],
        [0.5, 0.1],  # 0.1 degrees is ~11km > 0.0005 deg tolerance
        [1.0, 0.0],
    ]
    simplified = simplify_geometry(coords, tolerance_deg=0.0005)
    assert len(simplified) == 3
    assert simplified[1] == [0.5, 0.1]


def test_simplify_tolerance_threshold():
    # Very small deviation below tolerance
    coords = [
        [0.0, 0.0],
        [0.5, 0.0001],  # 0.0001 deg < 0.0005 deg tolerance
        [1.0, 0.0],
    ]
    simplified = simplify_geometry(coords, tolerance_deg=0.0005)
    assert len(simplified) == 2
