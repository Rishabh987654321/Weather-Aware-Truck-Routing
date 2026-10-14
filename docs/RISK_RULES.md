# Domain Risk Rules

This document outlines the risk scoring, hazard thresholds, load escalations, and route recommendation logic used by the Weather-Aware Truck Routing service.

---

## 1. Risk Levels

Risk levels are strictly ordered with numeric scores used for mile-weighted route averaging:

| Level | Score | Description |
|---|---|---|
| **Low** | 0 | Normal highway driving conditions |
| **Moderate** | 1 | Caution advised; minor weather effects |
| **High** | 2 | Adverse weather; increased stopping distance and wind deflection |
| **Severe** | 3 | Dangerous driving conditions; high rollover or loss-of-traction risk |
| **No Travel** | 4 | Prohibitive hazards; commercial vehicle movement must cease |
| **Unknown** | N/A | Excluded from numeric averages; tracked separately as `unknown_miles` |

---

## 2. Weather Thresholds

Weather conditions are evaluated at each checkpoint for the truck's estimated arrival time:

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| **Wind** (mph) | < 25 | 25–34 | 35–44 | 45–54 | >= 55 |
| **Rain** (in/hr) | < 0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | > 1.00 |
| **Snow** (in/hr) | < 0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | > 3.0 |

### Boundary Conventions:
- **Wind**: Lower-bound inclusive: `[0, 25) Low`, `[25, 35) Moderate`, `[35, 45) High`, `[45, 55) Severe`, `[55, ∞) No Travel`.
- **Rain**: Upper-bound inclusive: `< 0.10 Low`, `0.10 <= x <= 0.25 Moderate`, `0.25 < x <= 0.50 High`, `0.50 < x <= 1.00 Severe`, `> 1.00 No Travel`.
- **Snow**: Upper-bound inclusive: `< 0.5 Low`, `0.5 <= x <= 1.0 Moderate`, `1.0 < x <= 2.0 High`, `2.0 < x <= 3.0 Severe`, `> 3.0 No Travel`.

---

## 3. Checkpoint Evaluation & Load Escalations

1. Compute wind, rain, and snow risk levels independently for each checkpoint based on forecasted conditions at ETA.
2. Initial checkpoint level = **maximum** of the three condition levels.
3. Apply truck cargo weight (load) rules as **escalations only** (load can worsen risk, never lower it):

| Wind Speed | Cargo Load | Escalated Level | Rule Note |
|---|---|---|---|
| >= 55 mph | Any | **No Travel** | Critical wind hazard |
| 45–54 mph | > 30,000 lb | **No Travel** | High crosswind rollover risk on loaded trailer |
| 35–44 mph | > 40,000 lb | **Severe** (at least) | Heavy load handling deflection |

*Note: Load comparisons are strictly greater-than (`> 30,000` and `> 40,000`). Exact threshold weights do not trigger escalation.*

The deciding rules are recorded in `drivers[]` for transparency (e.g. `"wind 48 mph + load 34,000 lb -> No Travel"`).

---

## 4. Mile Attribution

- Each checkpoint owns a segment equal to the half-interval on either side, bounded by midpoints to its adjacent checkpoints.
- Origin (mile 0) and destination (final mile) checkpoints are always included.
- The sum of segment lengths across all levels equals the total route distance.

---

## 5. Recommendation Order & Tie-Breaking

Routes are evaluated through a tiered cascade:

1. **No Travel Miles** (Safety Gate): Any route with No Travel miles is eliminated if any route free of No Travel exists. If all routes contain No Travel, `recommended_route_id` is returned as `null` with a plain-language safety notice.
2. **Unknown Miles**: Routes with unforecasted segments are penalized.
3. **Severe Miles**: Minimize miles spent in severe conditions.
4. **High Miles**: Minimize miles spent in high-risk conditions.
5. **Average Risk Score**: Mile-weighted average across checkpoints (excluding unknown segments).
6. **Duration**: Shortest driving travel time.

### Tolerances:
- Candidate filter cascade evaluates tiers within `TIE_MILES = 5.0` (for miles) or `TIE_RISK = 0.05` (for average risk) of the minimum surviving value to allow subsequent criteria to break close ties.
- The plain-language `reason` string clearly communicates which criterion or tie-breaker decided the recommendation.

---

## 6. Checkpoint Spacing

Checkpoints are spaced dynamically along route polylines based on total distance:

| Route Distance | Checkpoint Interval |
|---|---|
| < 150 miles | Every 10 miles |
| 150 – 500 miles | Every 25 miles |
| > 500 miles | Every 50 miles |
