"""Route recommendation and ranking engine.

Pure Python logic: no Django, no I/O.
Source of truth: RULES.md section A5, ASSUMPTIONS.md #8, #9, #17, and Phase 1 review instructions.
"""

from typing import Any, Dict, List, Optional

from .config import TIE_MILES, TIE_RISK


def _get_val(route: Any, key: str, default: Any = 0.0) -> Any:
    """Helper to access dict key or object attribute."""
    if isinstance(route, dict):
        return route.get(key, default)
    return getattr(route, key, default)


def _get_miles(route: Any, level_key: str) -> float:
    """Extract miles for a specific risk level from route."""
    miles_by_level = _get_val(route, "miles_by_level", {})
    if isinstance(miles_by_level, dict):
        return float(miles_by_level.get(level_key, 0.0))
    return float(getattr(miles_by_level, level_key, 0.0))


def _get_route_id(route: Any) -> str:
    """Extract display ID for route."""
    val = _get_val(route, "id", "Route")
    val_str = str(val)
    if val_str.isdigit():
        return f"Route {val_str}"
    return val_str


def _get_duration_s(route: Any) -> float:
    """Extract duration in seconds."""
    return float(_get_val(route, "duration_s", 0.0))


def select_winner_cascade(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Order-independent filter cascade to select the single best route.

    Cascade order:
    1. unknown_miles (tolerance TIE_MILES)
    2. severe_miles (tolerance TIE_MILES)
    3. high_miles (tolerance TIE_MILES)
    4. avg_risk (tolerance TIE_RISK; None treated as worst)
    5. duration_s (shortest duration)

    At each tier, keep only candidates where (metric - min_metric) < tolerance.
    """
    if not candidates:
        raise ValueError("Cannot select winner from empty candidates.")
    if len(candidates) == 1:
        return candidates[0]

    survivors = list(candidates)

    tiers = [
        ("unknown_miles", lambda r: _get_miles(r, "unknown"), TIE_MILES),
        ("severe_miles", lambda r: _get_miles(r, "severe"), TIE_MILES),
        ("high_miles", lambda r: _get_miles(r, "high"), TIE_MILES),
        (
            "avg_risk",
            lambda r: (
                float("inf")
                if _get_val(r, "avg_risk") is None
                else float(_get_val(r, "avg_risk"))
            ),
            TIE_RISK,
        ),
    ]

    for _name, metric_fn, tolerance in tiers:
        if len(survivors) == 1:
            break
        min_metric = min(metric_fn(r) for r in survivors)
        survivors = [r for r in survivors if (metric_fn(r) - min_metric) < tolerance]

    if len(survivors) == 1:
        return survivors[0]

    # Tier 5: Shortest duration
    return min(survivors, key=_get_duration_s)


def _build_reason_text(winner: Dict[str, Any], runner_up: Dict[str, Any]) -> str:
    """Build explanation string naming deciding factor in plain language."""
    r_id = _get_route_id(runner_up)

    r_nt = _get_miles(runner_up, "no_travel")
    if r_nt > 0.0:
        return f"{r_id} blocked by No Travel weather ({round(r_nt)} mi)."

    # Tier 1: Unknown miles
    w_unk = _get_miles(winner, "unknown")
    r_unk = _get_miles(runner_up, "unknown")
    unk_diff = r_unk - w_unk
    if unk_diff >= TIE_MILES:
        return f"{r_id} has less forecast data."

    # Tier 2: Severe miles
    w_sev = _get_miles(winner, "severe")
    r_sev = _get_miles(runner_up, "severe")
    sev_diff = r_sev - w_sev

    if sev_diff >= TIE_MILES:
        if w_sev == 0.0:
            return f"No severe weather on this route. {r_id} has {round(r_sev)} mi."
        return f"Fewer severe weather miles ({round(w_sev)} mi vs {round(r_sev)} mi on {r_id})."

    # Tier 3: High miles
    w_high = _get_miles(winner, "high")
    r_high = _get_miles(runner_up, "high")
    high_diff = r_high - w_high

    if high_diff >= TIE_MILES:
        if w_high == 0.0:
            return f"No high-risk weather on this route. {r_id} has {round(r_high)} mi."
        return (
            f"Fewer high-risk weather miles ({round(w_high)} mi vs {round(r_high)} mi on {r_id})."
        )

    # Tier 4: Average risk
    w_risk_val: Optional[float] = _get_val(winner, "avg_risk")
    r_risk_val: Optional[float] = _get_val(runner_up, "avg_risk")

    w_risk = float("inf") if w_risk_val is None else float(w_risk_val)
    r_risk = float("inf") if r_risk_val is None else float(r_risk_val)

    if w_risk < float("inf") and r_risk == float("inf"):
        return f"{r_id} has less forecast data."

    risk_diff = r_risk - w_risk
    if risk_diff >= TIE_RISK:
        return f"Lower weather risk than {r_id}."

    # Tier 5: Duration
    w_dur = _get_duration_s(winner)
    r_dur = _get_duration_s(runner_up)
    dur_diff_min = (r_dur - w_dur) / 60.0
    dur_min_int = round(dur_diff_min)

    has_tolerance_diff = (
        0.0 < abs(unk_diff) < TIE_MILES
        or 0.0 < abs(sev_diff) < TIE_MILES
        or 0.0 < abs(high_diff) < TIE_MILES
        or 0.0 < abs(risk_diff) < TIE_RISK
    )

    if has_tolerance_diff:
        return "Weather risk is about the same, and this route is faster."

    if dur_min_int > 0:
        return f"Weather risk is the same, and this route is faster by {dur_min_int} min."
    return "Weather risk is the same, and this route is faster."


def rank_routes(routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rank routes and return recommended_route_id, reason, and ordered routes.

    Uses an order-independent filter cascade:
    1. Filter out routes with No Travel miles.
    2. Repeatedly run cascade to form ordered ranked list.
    3. Return None recommendation if all routes contain No Travel miles.
    """
    if not routes:
        return {
            "recommended_route_id": None,
            "reason": "No routes available.",
            "routes": [],
        }

    unblocked = [r for r in routes if _get_miles(r, "no_travel") == 0.0]
    blocked = [r for r in routes if _get_miles(r, "no_travel") > 0.0]

    # Handle all blocked case
    if not unblocked:
        remaining_blocked = list(blocked)
        ranked_blocked: List[Dict[str, Any]] = []
        while remaining_blocked:
            w = select_winner_cascade(remaining_blocked)
            ranked_blocked.append(w)
            remaining_blocked.remove(w)

        return {
            "recommended_route_id": None,
            "reason": (
                "All routes contain No Travel weather hazards. "
                "Consider departing at a later time."
            ),
            "routes": ranked_blocked,
        }

    # Repeatedly run cascade on unblocked routes
    remaining_unblocked = list(unblocked)
    ranked_unblocked: List[Dict[str, Any]] = []
    while remaining_unblocked:
        w = select_winner_cascade(remaining_unblocked)
        ranked_unblocked.append(w)
        remaining_unblocked.remove(w)

    # Rank blocked routes at the end
    remaining_blocked = list(blocked)
    ranked_blocked = []
    while remaining_blocked:
        w = select_winner_cascade(remaining_blocked)
        ranked_blocked.append(w)
        remaining_blocked.remove(w)

    ranked_routes = ranked_unblocked + ranked_blocked
    winner = ranked_routes[0]
    winner_id = _get_route_id(winner)

    if len(ranked_routes) > 1:
        reason = _build_reason_text(winner, ranked_routes[1])
    else:
        reason = "Safest route option available."

    return {
        "recommended_route_id": winner_id,
        "reason": reason,
        "routes": ranked_routes,
    }
