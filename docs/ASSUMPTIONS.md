# ASSUMPTIONS.md

The assignment leaves several points open. 

| # | Ambiguity | Decision | Why |
|---|---|---|---|
| 1 | "Sample every 10 / 25 / 50 miles" | Interval chosen by route length: <150 mi is 10, 150-500 mi is 25, >500 mi is 50. User can override. | Keeps checkpoint count reasonable on long trips while staying precise on short ones |
| 2 | Overlapping/gapped threshold ranges | Wind lower-inclusive; rain and snow upper-inclusive (see `RULES.md` A2) | The spec says No Travel is strictly `>1.00` / `>3.0`, so the boundary value belongs to Severe |
| 3 | Wind metric | Sustained wind (`wind_speed_10m`). Gusts are displayed in popups only. Single config switch. | Spec says "wind"; sustained is the standard reading |
| 4 | Snow units | Snowfall depth per hour in inches (Open-Meteo `snowfall`) | Spec says "in/hr" for snow |
| 5 | Rain + wind + snow together | Checkpoint level is the max of the three, then load escalation | Simple, explainable |
| 6 | Load rules | Escalate only, never lower. Strictly greater-than comparisons. | Matches spec wording |
| 7 | Miles per checkpoint | Each checkpoint owns half-intervals to its neighbours' midpoints | Miles-by-level sums exactly to route distance |
| 8 | No Travel and ranking | Routes with No Travel miles are never recommended over a legal route | A No Travel route is not safely drivable, so it should not win on shorter time |
| 9 | Strict ordering vs "balancing risk and time" | Lexicographic ranking with tie tolerance (5 mi, 0.05 risk) so time breaks near-ties | Avoids a 0.3-mile Severe difference overriding a multi-hour detour |
| 10 | Missing forecast data | Marked `Unknown`, excluded from averages, flagged in the UI | Never pretend missing data is safe |
| 11 | Heatmap slider baseline | Hours after departure (0-48) | Ties the heatmap to the trip being planned |
| 12 | Truck vs car routing | OSRM car profile with a 1.1x duration factor | No truck-routing key-free API; documented limitation |
| 13 | Driver rest/HOS | Not modeled | Out of scope per "correctness and clarity over extra features" |
| 14 | Timezones | UTC internally; display in the browser's timezone with the label | Avoids ETA/forecast mismatches |
| 15 | Forecast horizon | Departure must fall inside the forecast window; trip hours beyond the data get `Unknown` | Open-Meteo hourly data is limited in range |
| 16 | Single-checkpoint route edge case | Single checkpoint owns 100% of route distance | Preserves exact mile conservation for degenerate single-checkpoint paths |
| 17 | All-Unknown route scoring & unknown_miles | When all checkpoints are Unknown, avg_risk is None (treated as worst in recommender); unknown_miles tier penalizes routes with missing data | Avoids misleading 0.0 risk score and ensures routes with real data beat unknown routes |
| 18 | Unknown miles in ranking | After the No Travel gate, routes are compared on `unknown_miles` (tolerance `TIE_MILES`) before Severe miles. When this tier decides, `reason` says so. | A route we can't see weather for must not win just because its bad weather is invisible |
| 19 | Tie-tolerance method | Order-independent filter cascade: at each tier keep routes within tolerance of the minimum, then move to the next tier. Not a pairwise comparison sort. | Tolerance-based "equal" is not transitive, so a comparison sort could pick different winners depending on input order |