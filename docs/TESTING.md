# Testing & Verification Guide

This document covers automated test suites, quality gates, and the manual test matrix for the Weather-Aware Truck Routing system.

---

## 1. Automated Test Suites

### Backend Tests (`pytest`)
- **Suite**: 138 automated unit and integration tests covering:
  - Routing & OSRM client (`test_osrm.py`)
  - Weather fetching, chunking & grid caching (`test_open_meteo.py`, `test_corridor.py`)
  - Checkpoint interpolation & geometry (`test_checkpoints.py`, `test_geometry.py`)
  - Risk evaluation & load rules (`test_rules.py`, `test_intensity.py`, `test_scoring.py`)
  - Recommendation engine & tie breaking (`test_recommend.py`)
  - REST API contracts & validation (`test_api.py`, `test_heatmap_api.py`, `test_health.py`, `test_geocode.py`)
- **Command**:
  ```bash
  cd backend
  pytest
  ```

### Frontend Tests (`vitest`)
- **Suite**: 25 automated component and integration tests covering:
  - Formatters, duration delta, and time translation (`format.test.js`)
  - Form validation & field disabling (`App.test.jsx`)
  - Recommended badge and ID translation (`App.test.jsx`)
  - Timeline slider controls, play/pause, and disabled states (`HeatmapSlider.test.jsx`)
  - Checkpoint marker DOM stability across 10 ticks (`Phase6Regression.test.jsx`)
  - Delta pill calculation relative to selected route across 3 routes (`Phase6Regression.test.jsx`)
- **Command**:
  ```bash
  cd frontend
  npm test
  ```

---

## 2. Code Quality & Linting Gates

### Backend
```bash
cd backend
ruff check .
black --check .
```

### Frontend
```bash
cd frontend
npm run lint
npx prettier --check "src/**/*.{js,jsx,css,json}"
```

---

## 3. Section 9: Manual Verification Matrix

The following scenarios verify real-world behavior and edge cases in the application:

| Check | Scenario / Parameters | Expected Behavior | Result |
|---|---|---|---|
| **9.1 Long Trip** | Dallas, TX to Denver, CO (~790 mi) | 3 alternative routes displayed, checkpoints sampled every 50 miles, bounds fit properly with docked panel padding. | **PASS** |
| **9.2 Short Trip** | Dallas, TX to Fort Worth, TX (~32 mi) | Checkpoints sampled every 10 miles, origin and destination pins positioned with readable labels, no intermediate clutter. | **PASS** |
| **9.3 Mid Trip** | Chicago, IL to Atlanta, GA (~710 mi) | Real-world weather corridor with multi-state route comparison and ETA tracking. | **PASS** |
| **9.4 Load Escalation** | 42,000 lb vs 25,000 lb on route with 38 mph winds | 42,000 lb escalates from Moderate to Severe (`wind 38 mph + load 42,000 lb -> at least Severe`). 25,000 lb remains Moderate. | **PASS** |
| **9.5 Departure Out of Range** | Departure date set > 16 days ahead or in the past | API returns validation error `400 Bad Request` with clear message `"Departure time must be between now and 16 days ahead."` | **PASS** |
| **9.6 Slider Smoothness** | Scrubbing 0–48h timeline with 3 routes active | No network requests fired during scrubbing; route polylines and checkpoint markers never re-render; heat canvas updates smoothly. | **PASS** |
| **9.7 Real-Data Hotspot** | Chicago to Atlanta at +11h and +12h | Clearly visible red/orange hotspot around Indianapolis to Cincinnati corridor, fading to calm elsewhere. | **PASS** |
| **9.8 Calm Corridor Note** | Any hour where corridor maximum intensity < 0.25 | Badge appears in control bar: *"Forecast is calm along this corridor at this hour."* | **PASS** |
| **9.9 Heatmap Toggle** | Toggling heatmap layer from On to Off | Playback immediately pauses, slider and play buttons become disabled (opacity 0.4), legend is dimmed (opacity 0.35), heat canvas detached from map. | **PASS** |
| **9.10 Mobile Layout** | Viewport width 390px (e.g. iPhone 14) | Bottom sheet with snap points (peek, half, full), horizontal scroll prevented, timeline controls compact and usable. | **PASS** |
