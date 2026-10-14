"""Geometry utilities for route simplification and spatial calculations.

Implements iterative Ramer-Douglas-Peucker line simplification to reduce
GeoJSON route payload size while keeping full precision internally for
checkpoint placement.
Source of truth: ARCHITECTURE.md section 6 and Phase4.md.
"""

from typing import List


def _perpendicular_dist_sq(
    pt: List[float], line_start: List[float], line_end: List[float]
) -> float:
    """Compute squared perpendicular distance from pt to segment between line_start and line_end."""
    x0, y0 = pt[0], pt[1]
    x1, y1 = line_start[0], line_start[1]
    x2, y2 = line_end[0], line_end[1]

    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq <= 1e-12:
        return (x0 - x1) * (x0 - x1) + (y0 - y1) * (y0 - y1)

    # Cross product gives 2 * triangle area
    cross = dy * x0 - dx * y0 + x2 * y1 - y2 * x1
    return (cross * cross) / seg_len_sq


def simplify_geometry(
    coords: List[List[float]], tolerance_deg: float = 0.0005
) -> List[List[float]]:
    """Simplify GeoJSON coordinates [[lon, lat], ...] using iterative Ramer-Douglas-Peucker.

    Args:
        coords: List of [lon, lat] coordinate pairs.
        tolerance_deg: Maximum allowable perpendicular deviation in degrees (~0.0005 deg is ~55m).

    Returns:
        Simplified list of [lon, lat] coordinate pairs preserving endpoints.
    """
    n = len(coords)
    if n <= 2:
        return [list(c) for c in coords]

    tol_sq = tolerance_deg * tolerance_deg
    keep = [False] * n
    keep[0] = True
    keep[-1] = True

    stack = [(0, n - 1)]

    while stack:
        start_idx, end_idx = stack.pop()
        start = coords[start_idx]
        end = coords[end_idx]

        max_dist_sq = 0.0
        max_idx = -1

        for i in range(start_idx + 1, end_idx):
            d_sq = _perpendicular_dist_sq(coords[i], start, end)
            if d_sq > max_dist_sq:
                max_dist_sq = d_sq
                max_idx = i

        if max_dist_sq > tol_sq and max_idx != -1:
            keep[max_idx] = True
            stack.append((start_idx, max_idx))
            stack.append((max_idx, end_idx))

    return [coords[i] for i in range(n) if keep[i]]
