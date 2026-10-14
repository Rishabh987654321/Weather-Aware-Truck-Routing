# ARCHITECTURE.md

## 1. System overview

```
Browser (React)                     Django (DRF)                      External APIs
---------------                     ------------                      -------------
SearchForm  --GET /api/geocode-->   geocode service   ------------->  Nominatim
SearchForm  --POST /api/analyze->   analyze view
                                      routing service  ------------->  OSRM
                                      checkpoint builder
                                      weather service  ------------->  Open-Meteo (batched)
                                      risk engine (pure)
                                      recommender
HeatmapSlider --POST /api/heatmap->  corridor service  ------------->  Open-Meteo (batched, 48h)
```

`/api/analyze` and `/api/heatmap` are called in parallel by the frontend after the user presses Analyze.

## 2. Backend modules

| Module | Responsibility |
|---|---|
| `services/geocode.py` | Nominatim search, cached, 1 req/sec courtesy, User-Agent set |
| `services/osrm.py` | Fetch up to 3 alternative routes; via-waypoint fallback when fewer than 3 come back; dedupe near-identical routes |
| `services/open_meteo.py` | Batched hourly fetch (wind mph, rain in, snowfall in), thread pool, grid-cell cache |
| `services/corridor.py` | Build the heatmap grid from the union of route geometries |
| `risk/rules.py` | Threshold classification, load-rule escalation (pure) |
| `risk/scoring.py` | Mile attribution, miles-by-level, avg risk (pure) |
| `risk/recommend.py` | Ranking tuple with tie tolerance and reason text (pure) |
| `risk/config.py` | All constants: thresholds, tolerances, spacing table, truck speed factor |
| `api/` | DRF views and serializers (validation and response shaping only) |

## 3. Analyze pipeline

1. **Validate** input (coords, departure time, load).
2. **Routes:** call OSRM with `alternatives=3&overview=full&geometries=geojson&annotations=distance,duration`. If fewer than 3 distinct routes return, create via-waypoints (midpoint offset perpendicular by ~10-15% of route length) and re-route. Drop routes sharing over ~90% geometry.
3. **Cumulative table:** from annotations, build cumulative miles and seconds at each coordinate. Apply the truck speed factor (default 1.1x duration).
4. **Checkpoints:** choose the interval by route length (`RULES.md` A6). Find the coordinate at each mile mark by interpolating the cumulative table.
5. **ETA:** `departure_utc + cumulative_seconds`.
6. **Weather:** snap checkpoints to a 0.1 degree grid, dedupe across routes, batch into Open-Meteo requests in parallel, cache by cell and fetch hour.
7. **Interpolate:** linearly interpolate the two surrounding hourly values to each ETA. If the ETA is outside the returned window, mark `Unknown`.
8. **Classify:** `risk.rules.classify_checkpoint(wind, rain, snow, load_lb)`.
9. **Score:** `risk.scoring.summarize_route(checkpoints, distance)` gives miles-by-level and avg risk.
10. **Recommend:** `risk.recommend.rank(routes)` gives the recommended id and reason.

## 4. Heatmap pipeline

1. Build a corridor grid from all route geometries: a point every 20-25 miles along each route, plus 2 lateral offsets (about +/-10-20 miles) per point. Dedupe on the 0.1 degree grid.
2. Fetch 49 hourly values (hour 0 to 48 from departure) per grid point in batches.
3. Convert each hour to a **continuous intensity 0..1** (piecewise-linear across thresholds, load escalation applied) so the colour gradient is smooth.
4. Return grid points with an intensity array of 49 values each. The client holds all of it and moves the slider with no network calls.

## 5. Data model (no database needed)

The app is stateless. No Django models are required beyond defaults. Caching uses Django's cache framework (locmem for dev, Redis if hosted).

Key types:

```
Checkpoint { mile, lat, lon, eta_utc, wind_mph, rain_in_hr, snow_in_hr,
             level, score, drivers[] }
Route      { id, geometry, distance_mi, duration_s, checkpoints[],
             miles_by_level{}, avg_risk, blocked }
```

## 6. Frontend architecture

- **State (Zustand):** `form`, `analysis`, `selectedRouteId`, `heatmap`, `heatHour`, `layers`.
- **Components:** `SearchForm`, `RouteCards`, `MapView`, `CheckpointMarkers`, `HeatLayer`, `HeatmapSlider`.
- **Data flow:** submit, then two parallel requests, then store. Route selection and slider are local interactions on stored data.
- **Performance:** canvas renderer, simplified geometry, memoized layers, heat layer updated via ref with `requestAnimationFrame` throttling.

## 7. Error handling

| Case | Behaviour |
|---|---|
| Geocode finds nothing | 404 with message; UI shows inline field error |
| OSRM no route | 422 "No drivable route"; UI empty state |
| OSRM returns fewer than 3 | Via-waypoint fallback; if still fewer, return what exists and note it |
| Open-Meteo failure or timeout | Retry once; then mark affected checkpoints `Unknown` and return a warning |
| Departure outside forecast window | 400 with allowed window |
| All routes blocked | `recommended_route_id: null` plus message |

## 8. Deployment

- Backend: Render or Railway (gunicorn + whitenoise), env vars from `README.md`.
- Frontend: Vercel or Netlify, `VITE_API_BASE_URL` pointing at the backend.
- CORS limited to the frontend origin.
- DRF throttling on `/api/geocode` and `/api/analyze`.