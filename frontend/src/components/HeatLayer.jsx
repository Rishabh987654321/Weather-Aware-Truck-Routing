import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';
import { useTripStore } from '../store/useTripStore';

// Monkey-patch L.HeatLayer to:
// 1. Respect custom panes (leaflet.heat hardcodes map._panes.overlayPane)
// 2. Prevent "Cannot read properties of null (reading 'getSize')" when layer is detached/removed
if (L.HeatLayer && !L.HeatLayer.prototype.__patchedSafePaneRedraw) {
  L.HeatLayer.prototype.onAdd = function (map) {
    this._map = map;
    if (!this._canvas) {
      this._initCanvas();
    }

    // Append canvas to custom pane if specified, falling back to overlayPane
    const paneName = this.options.pane || 'heatmapPane';
    const targetPane = map.getPane(paneName) || map._panes.overlayPane;
    targetPane.appendChild(this._canvas);

    map.on('moveend', this._reset, this);
    if (map.options.zoomAnimation && L.Browser.any3d) {
      map.on('zoomanim', this._animateZoom, this);
    }
    this._reset();
    return this;
  };

  L.HeatLayer.prototype.onRemove = function (map) {
    if (this._frame) {
      L.Util.cancelAnimFrame(this._frame);
      this._frame = null;
    }
    if (this._canvas && this._canvas.parentNode) {
      this._canvas.parentNode.removeChild(this._canvas);
    }
    map.off('moveend', this._reset, this);
    if (map.options.zoomAnimation) {
      map.off('zoomanim', this._animateZoom, this);
    }
    return this;
  };

  const originalRedraw = L.HeatLayer.prototype._redraw;
  L.HeatLayer.prototype._redraw = function () {
    if (!this._map) {
      if (this._frame) {
        L.Util.cancelAnimFrame(this._frame);
        this._frame = null;
      }
      return;
    }
    return originalRedraw.apply(this, arguments);
  };

  const originalRedrawMethod = L.HeatLayer.prototype.redraw;
  L.HeatLayer.prototype.redraw = function () {
    if (!this._map) return this;
    return originalRedrawMethod.apply(this, arguments);
  };

  const originalSetLatLngs = L.HeatLayer.prototype.setLatLngs;
  L.HeatLayer.prototype.setLatLngs = function (latlngs) {
    this._latlngs = latlngs;
    if (!this._map) return this;
    return originalSetLatLngs.call(this, latlngs);
  };

  L.HeatLayer.prototype.__patchedSafePaneRedraw = true;
}

/**
 * Dynamic radius scaling based on map zoom level.
 */
function getRadiusForZoom(zoom) {
  return Math.max(16, Math.min(48, Math.round(zoom * 3.8)));
}

/**
 * Builds heatmap gradient reading colors strictly from CSS tokens.
 * Matches DESIGN_SYSTEM.md section 11:
 * --risk-low-alpha at 0.15, --risk-low at 0.35, --risk-moderate at 0.55,
 * --risk-high at 0.75, --risk-severe at 0.90, --risk-no-travel at 1.0.
 */
function getHeatGradient() {
  if (typeof window === 'undefined') return {};
  const s = getComputedStyle(document.documentElement);
  const lowAlpha = s.getPropertyValue('--risk-low-alpha').trim() || 'rgba(46, 158, 106, 0.25)';
  const low = s.getPropertyValue('--risk-low').trim() || '#2E9E6A';
  const mod = s.getPropertyValue('--risk-moderate').trim() || '#F2C200';
  const high = s.getPropertyValue('--risk-high').trim() || '#EE7B1C';
  const severe = s.getPropertyValue('--risk-severe').trim() || '#D1322F';
  const noTravel = s.getPropertyValue('--risk-no-travel').trim() || '#1B1B1F';

  return {
    0.15: lowAlpha,
    0.35: low,
    0.55: mod,
    0.75: high,
    0.90: severe,
    1.0: noTravel,
  };
}

/**
 * Client-side intensity remapping so Low weather (0.01 - 0.25) is a faint but
 * clearly visible soft green, scaling smoothly through Moderate, High, and Severe.
 */
function remapIntensity(r) {
  if (r <= 0) return 0;
  if (r <= 0.25) {
    // Low: 0.20 -> 0.42 (visible green tint)
    return 0.20 + (r / 0.25) * 0.22;
  }
  if (r <= 0.50) {
    // Moderate: 0.42 -> 0.65 (yellow)
    return 0.42 + ((r - 0.25) / 0.25) * 0.23;
  }
  if (r <= 0.75) {
    // High: 0.65 -> 0.85 (orange)
    return 0.65 + ((r - 0.50) / 0.25) * 0.20;
  }
  // Severe / No Travel: 0.85 -> 1.00 (red / dark)
  return 0.85 + ((r - 0.75) / 0.25) * 0.15;
}

/**
 * HeatLayer renders leaflet.heat imperatively with zero React re-renders on slider movement.
 */
export function HeatLayer() {
  const map = useMap();
  const heatLayerRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    // 1. Ensure dedicated heatmapPane exists below polylines & markers (zIndex 350)
    let pane = map.getPane('heatmapPane');
    if (!pane) {
      pane = map.createPane('heatmapPane');
      pane.style.zIndex = '350';
    }

    const gradient = getHeatGradient();
    const initialRadius = getRadiusForZoom(map.getZoom());

    const layer = L.heatLayer([], {
      pane: 'heatmapPane',
      radius: initialRadius,
      blur: 18,
      max: 1.0,
      maxZoom: 1, // Crucial: prevents leaflet.heat from scaling down intensity by 2^(maxZoom - zoom)
      minOpacity: 0.18,
      gradient,
    });

    if (useTripStore.getState().showHeatmap) {
      layer.addTo(map);
    }
    heatLayerRef.current = layer;

    // Zoom listener for dynamic radius scaling
    const onZoom = () => {
      const active = heatLayerRef.current;
      if (active && active._map) {
        active.setOptions({
          radius: getRadiusForZoom(map.getZoom()),
        });
      }
    };
    map.on('zoomend', onZoom);

    // 2. Helper to update points imperatively for hour h
    const updatePointsForHour = (hour) => {
      const { heatmap, showHeatmap } = useTripStore.getState();
      const active = heatLayerRef.current;
      if (!active || !active._map) return;

      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }

      if (!heatmap?.points || !showHeatmap) {
        active.setLatLngs([]);
        return;
      }

      rafRef.current = requestAnimationFrame(() => {
        const currentActive = heatLayerRef.current;
        if (!currentActive || !currentActive._map) return;

        const t0 = performance.now();
        const pts = [];
        const h = Math.max(0, Math.min(48, hour));
        const numPoints = heatmap.points.length;
        let maxRaw = 0;
        let sumRaw = 0;
        let rawCount = 0;

        for (let i = 0; i < numPoints; i++) {
          const pt = heatmap.points[i];
          const raw = pt.intensity?.[h] || 0;
          if (raw > 0) {
            rawCount++;
            sumRaw += raw;
            if (raw > maxRaw) maxRaw = raw;
            pts.push([pt.lat, pt.lon, remapIntensity(raw)]);
          }
        }

        const meanRaw = rawCount > 0 ? sumRaw / rawCount : 0;
        console.log(
          `[HeatLayer] Hour +${h}h: max=${maxRaw.toFixed(3)}, mean=${meanRaw.toFixed(3)}, activePoints=${rawCount}/${numPoints}`
        );

        currentActive.setLatLngs(pts);
        window.__lastHeatRepaintMs = performance.now() - t0;
      });
    };

    // Initial paint
    updatePointsForHour(useTripStore.getState().heatHour);

    // 3. Subscribe to Zustand store changes outside React render cycle
    const unsubHour = useTripStore.subscribe(
      (state) => state.heatHour,
      (newHour) => {
        updatePointsForHour(newHour);
      }
    );

    const unsubHeatmap = useTripStore.subscribe(
      (state) => state.heatmap,
      () => {
        updatePointsForHour(useTripStore.getState().heatHour);
      }
    );

    const unsubToggle = useTripStore.subscribe(
      (state) => state.showHeatmap,
      (show) => {
        const active = heatLayerRef.current;
        if (!active) return;
        if (rafRef.current) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        if (show) {
          if (!map.hasLayer(active)) {
            active.addTo(map);
          }
          updatePointsForHour(useTripStore.getState().heatHour);
        } else {
          if (map.hasLayer(active)) {
            active.setLatLngs([]);
            map.removeLayer(active);
          }
        }
      }
    );

    return () => {
      map.off('zoomend', onZoom);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      unsubHour();
      unsubHeatmap();
      unsubToggle();
      const active = heatLayerRef.current;
      if (active && map.hasLayer(active)) {
        map.removeLayer(active);
      }
      heatLayerRef.current = null;
    };
  }, [map]);

  return null;
}
