# API.md

Base URL: `/api`. All bodies are JSON. Times are ISO 8601; the server converts to UTC.

## GET /api/geocode?q=<text>

Returns up to 5 matches.

```json
{ "results": [ { "label": "Dallas, TX, USA", "lat": 32.7767, "lon": -96.797 } ] }
```

Errors: `400` missing/short `q`, `429` throttled.

## POST /api/analyze

Request:

```json
{
  "origin":      { "lat": 32.7767, "lon": -96.797, "label": "Dallas, TX" },
  "destination": { "lat": 39.7392, "lon": -104.9903, "label": "Denver, CO" },
  "departure_time": "2026-10-14T06:00:00-05:00",
  "load_lbs": 42000,
  "checkpoint_interval_mi": null
}
```

`checkpoint_interval_mi`: optional override; one of 10, 25, 50. `null` means automatic by route length.

Response:

```json
{
  "recommended_route_id": "r2",
  "reason": "0 Severe miles vs 12 on r1; 41 min slower.",
  "warnings": [],
  "routes": [
    {
      "id": "r2",
      "geometry": [[-96.797, 32.7767], [-96.8, 32.78]],
      "distance_mi": 802.4,
      "duration_s": 43200,
      "interval_mi": 50,
      "blocked": false,
      "avg_risk": 0.42,
      "miles_by_level": {
        "low": 600.0, "moderate": 150.0, "high": 52.4,
        "severe": 0.0, "no_travel": 0.0, "unknown": 0.0
      },
      "checkpoints": [
        {
          "mile": 50,
          "lat": 33.5, "lon": -97.1,
          "eta": "2026-10-14T07:10:00Z",
          "wind_mph": 22.1,
          "gust_mph": 28.4,
          "rain_in_hr": 0.0,
          "snow_in_hr": 0.0,
          "level": "low",
          "drivers": []
        }
      ]
    }
  ],
  "timings_ms": {
    "osrm_primary": 1820.5,
    "osrm_fallback": 0.0,
    "weather": 2100.2,
    "scoring": 12.1,
    "serialization": 24.3
  }
}
```

`level` is one of `low | moderate | high | severe | no_travel | unknown`.
`avg_risk` is nullable (`float | null`), returning `null` when all checkpoints are `unknown` (per ASSUMPTIONS.md #17).
`gust_mph` is nullable (`float | null`), provided for driver situational awareness per ASSUMPTIONS.md #3.
`timings_ms` is an optional/debug latency breakdown across internal pipeline stages.

Errors:

| Status | Meaning |
|---|---|
| 400 | Invalid input (coords, load <= 0, departure outside forecast window) |
| 422 | No drivable route |
| 502 | Upstream (OSRM) failure |

Weather upstream failures do not fail the request. Affected checkpoints become `unknown` and `warnings[]` explains.

## POST /api/heatmap

Request: same `origin`, `destination`, `departure_time`, `load_lbs` as analyze (the server reuses cached routes when possible).

Response:

```json
{
  "start_time": "2026-10-14T11:00:00Z",
  "hours": 49,
  "points": [
    { "lat": 33.5, "lon": -97.1, "intensity": [0.1, 0.1, 0.2, 0.3] }
  ]
}
```

`intensity` has `hours` values (0..1), index 0 is the departure hour (rounded down to the hour), index 48 is +48h. Values include load-rule escalation.