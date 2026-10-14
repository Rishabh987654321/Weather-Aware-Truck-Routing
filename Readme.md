# Weather-Aware Truck Routing

A React + Django web app that helps a truck driver pick the safest route based on **weather, load weight, and travel time**.

## What it does

Input: origin, destination, departure date/time, load weight (lb).

Output:
- 3 route options (routing API)
- Weather sampled at checkpoints every 10 / 25 / 50 miles, using the truck's **ETA at each checkpoint**
- Risk level per checkpoint (Low, Moderate, High, Severe, No Travel) using the provided threshold and load rules
- A recommended route (fewest Severe miles, then High miles, then lowest avg risk, then shortest time)
- Map with all routes, checkpoints, risk levels, ETAs, route summaries
- Weather heatmap along the trip corridor with a 0-48 hour forecast slider

## Stack

| Layer | Choice |
|---|---|
| Frontend | Vite + React, Zustand, MUI, react-leaflet, leaflet.heat |
| Backend | Django + Django REST Framework |
| Routing | OSRM public API (3 alternatives) |
| Geocoding | Nominatim (proxied by Django) |
| Weather | Open-Meteo (hourly wind, rain, snowfall; no API key) |

No API keys are required.

## Repo layout

```
backend/
  config/          Django settings, CORS, throttling
  api/             views, serializers, urls
  services/        osrm.py, geocode.py, open_meteo.py, corridor.py
  risk/            rules.py, scoring.py, recommend.py  (pure functions, no I/O)
  tests/           unit tests + mocked HTTP fixtures
frontend/
  src/components/  SearchForm, RouteCards, MapView, HeatmapSlider
  src/store/       useTripStore.js
  src/api/         client.js
docs/              (the .md files listed below)
```

## Quick start

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver        # http://localhost:8000

# frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Environment variables:

| Var | Where | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | backend | Django secret |
| `ALLOWED_HOSTS` | backend | comma-separated hosts |
| `CORS_ALLOWED_ORIGINS` | backend | frontend origin(s) |
| `CONTACT_EMAIL` | backend | goes in the User-Agent for Nominatim/OSRM requests |
| `VITE_API_BASE_URL` | frontend | backend URL |

## Documentation index

| File | Read it for |
|---|---|
| `AGENTS.md` | Entry point for the AI agent: read order and ground rules |
| `RULES.md` | Domain risk rules (source of truth) and coding rules |
| `ARCHITECTURE.md` | System design, pipeline, modules, caching |
| `API.md` | Endpoint contracts |
| `DESIGN.md` | UI/UX and map/heatmap behaviour |
| `PHASES.md` | Build order with done-criteria |
| `TESTING.md` | Test plan and required cases |
| `ASSUMPTIONS.md` | Interpretation of ambiguous spec points |
| `LOOM.md` | 5-10 min walkthrough script |

## Known limitations

- OSRM public server is car-profile only, not truck-specific.
- Driver hours-of-service and rest stops are not modeled in ETAs.
- Free public APIs have usage policies and rate limits; the backend caches and proxies them.

## Deliverables checklist

- [ ] GitHub repository
- [ ] Hosted application
- [ ] 5-10 min Loom walkthrough