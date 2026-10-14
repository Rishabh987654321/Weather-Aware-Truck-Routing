import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Pane, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  computeRouteStretches,
  filterVisibleCheckpoints,
  formatDurationDelta,
  formatLocalTime,
  RISK_LEVELS,
} from '../utils/format';
import { segmentRouteGeometry } from '../utils/geometry';
import { HeatLayer } from './HeatLayer';

// Resolved color lookup strictly from CSS tokens for Canvas 2D compatibility
function getResolvedThemeColors() {
  if (typeof window === 'undefined') {
    return {
      white: '#FFFFFF',
      ink3: '#5F6A70',
      primary: '#1456A0',
      risk: {
        low: '#2E9E6A',
        moderate: '#F2C200',
        high: '#EE7B1C',
        severe: '#D1322F',
        no_travel: '#1B1B1F',
        unknown: '#9AA3A8',
      },
    };
  }
  const s = getComputedStyle(document.documentElement);
  return {
    white: s.getPropertyValue('--white').trim() || '#FFFFFF',
    ink3: s.getPropertyValue('--ink-3').trim() || '#5F6A70',
    primary: s.getPropertyValue('--primary').trim() || '#1456A0',
    risk: {
      low: s.getPropertyValue('--risk-low').trim() || '#2E9E6A',
      moderate: s.getPropertyValue('--risk-moderate').trim() || '#F2C200',
      high: s.getPropertyValue('--risk-high').trim() || '#EE7B1C',
      severe: s.getPropertyValue('--risk-severe').trim() || '#D1322F',
      no_travel: s.getPropertyValue('--risk-no-travel').trim() || '#1B1B1F',
      unknown: s.getPropertyValue('--risk-unknown').trim() || '#9AA3A8',
    },
  };
}

const BASE_TILE_URL =
  import.meta.env.VITE_TILE_URL ||
  'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

const BASE_TILE_ATTRIBUTION =
  import.meta.env.VITE_TILE_ATTRIBUTION ||
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

const LABELS_TILE_URL = import.meta.env.VITE_LABELS_TILE_URL || '';

const handleTileError = (e) => {
  if (e?.tile) {
    e.tile.style.visibility = 'hidden';
  }
};

// Checkpoint icon cache to preserve DOM identity across ticks
const checkpointIconCache = new Map();
function getCheckpointIcon(level, letter, isHovered, i = 0) {
  const key = `${level}-${letter}-${isHovered ? 1 : 0}-${i}`;
  if (!checkpointIconCache.has(key)) {
    const selectedClass = isHovered ? ' cp__dot--selected' : '';
    checkpointIconCache.set(
      key,
      L.divIcon({
        className: 'cp',
        html: `<span class="cp__dot level-${level}${selectedClass}" style="--i:${i}">${letter}</span>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
        popupAnchor: [0, -12],
      })
    );
  }
  return checkpointIconCache.get(key);
}

function createPinIcon(type, label) {
  const isDest = type === 'destination';
  const shapeStyle = isDest
    ? 'width: 14px; height: 14px; background: var(--ink); border: 2px solid var(--white); box-shadow: 0 0 0 2px var(--white), 0 2px 6px rgba(20,24,27,0.35);'
    : 'width: 14px; height: 14px; border-radius: 50%; background: var(--primary); border: 2px solid var(--white); box-shadow: 0 0 0 2px var(--ink), 0 2px 6px rgba(20,24,27,0.35);';

  return L.divIcon({
    className: 'pin-marker',
    html: `
      <div style="display: flex; flex-direction: column; align-items: center; pointer-events: none;">
        <div style="${shapeStyle}"></div>
        <div style="
          margin-top: 4px;
          background: var(--field);
          border: 1px solid var(--line);
          border-radius: var(--r-sm);
          padding: 2px 6px;
          font-family: var(--font-display);
          font-size: 12px;
          font-weight: 600;
          color: var(--ink);
          white-space: nowrap;
          text-shadow: 0 0 3px var(--white), 0 0 6px var(--white), 0 0 8px var(--white);
          box-shadow: 0 0 0 2px var(--white), 0 2px 8px rgba(20,24,27,0.25);
        ">${label}</div>
      </div>
    `,
    iconSize: [60, 40],
    iconAnchor: [30, 7],
  });
}

// Delta pill cache to preserve DOM identity across ticks
const deltaPillCache = new Map();
function getDeltaPillIcon(text) {
  if (!deltaPillCache.has(text)) {
    deltaPillCache.set(
      text,
      L.divIcon({
        className: 'delta-pill-container',
        html: `<div class="delta-pill">${text}</div>`,
        iconSize: [60, 24],
        iconAnchor: [30, 12],
      })
    );
  }
  return deltaPillCache.get(text);
}

// Controller to handle bounds fitting and responsiveness
function MapController({ routes, origin, destination, isMobile }) {
  const map = useMap();

  useEffect(() => {
    if (!routes || routes.length === 0) {
      if (origin && destination) {
        const bounds = L.latLngBounds(
          [origin.lat, origin.lon],
          [destination.lat, destination.lon]
        );
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 9 });
      }
      return;
    }

    const allCoords = [];
    routes.forEach((r) => {
      r.geometry.forEach(([lon, lat]) => allCoords.push([lat, lon]));
    });

    if (allCoords.length > 0) {
      const bounds = L.latLngBounds(allCoords);
      // Desktop: padding-left 460px for docked panel; Mobile: padding-bottom 160px for sheet peek
      const padding = isMobile
        ? { paddingTop: 40, paddingBottom: 160, paddingLeft: 20, paddingRight: 20 }
        : { paddingTop: 60, paddingBottom: 60, paddingLeft: 460, paddingRight: 60 };

      // Fit bounds with zoomSnap 0.25 and padding for panel (desktop) or sheet (mobile)
      map.fitBounds(bounds, {
        paddingTopLeft: [padding.paddingLeft, padding.paddingTop],
        paddingBottomRight: [padding.paddingRight, padding.paddingBottom],
        maxZoom: 12,
        animate: true,
        duration: 0.8,
      });
    }
  }, [routes, origin, destination, isMobile, map]);

  return null;
}

export function MapView({
  routes = [],
  selectedRouteId = null,
  onSelectRoute = () => {},
  origin = null,
  destination = null,
  isLoading = false,
  activeCheckpointIndex = null,
  isMobile = false,
}) {
  const mapRef = useRef(null);
  const themeColors = useMemo(() => getResolvedThemeColors(), []);

  const selectedRoute = useMemo(
    () => routes.find((r) => r.id === selectedRouteId) || routes[0],
    [routes, selectedRouteId]
  );

  const alternateRoutes = useMemo(
    () => routes.filter((r) => r.id !== selectedRoute?.id),
    [routes, selectedRoute]
  );

  // Stretches and segmented geometry for the selected route
  const selectedSegments = useMemo(() => {
    if (!selectedRoute) return [];
    const stretches = computeRouteStretches(selectedRoute);
    return segmentRouteGeometry(selectedRoute, stretches);
  }, [selectedRoute]);

  // Full casing coordinates for selected route
  const casingCoords = useMemo(() => {
    if (!selectedRoute?.geometry) return [];
    return selectedRoute.geometry.map(([lon, lat]) => [lat, lon]);
  }, [selectedRoute]);

  // Destination ETA label
  const destEtaLabel = useMemo(() => {
    if (!selectedRoute?.checkpoints?.length) return 'Destination';
    const lastCp = selectedRoute.checkpoints[selectedRoute.checkpoints.length - 1];
    return `Destination (${formatLocalTime(lastCp.eta || lastCp.eta_utc)})`;
  }, [selectedRoute]);

  // Filter out checkpoint markers at mile 0 or at the final mile
  const visibleCheckpoints = useMemo(
    () => filterVisibleCheckpoints(selectedRoute?.checkpoints, selectedRoute?.distance_mi),
    [selectedRoute]
  );

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Map corner label */}
      <div
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          zIndex: 500,
          background: 'rgba(255, 255, 255, 0.92)',
          backdropFilter: 'blur(4px)',
          border: '1px solid var(--line)',
          borderRadius: 'var(--r-sm)',
          padding: '6px 12px',
          fontFamily: 'var(--font-display)',
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--ink-2)',
          boxShadow: '0 2px 8px rgba(20, 24, 27, 0.08)',
          pointerEvents: 'none',
        }}
      >
        Weather at your ETA
      </div>

      <MapContainer
        preferCanvas
        center={[39.0, -98.0]}
        zoom={4}
        maxZoom={12}
        zoomSnap={0.25}
        zoomControl={false}
        style={{ width: '100%', height: '100%', background: 'var(--ground)' }}
        ref={mapRef}
      >
        {/* Basemap layer (defaults to OpenStreetMap, configurable via VITE_TILE_URL) */}
        <TileLayer
          url={BASE_TILE_URL}
          attribution={BASE_TILE_ATTRIBUTION}
          maxZoom={12}
          eventHandlers={{ tileerror: handleTileError }}
        />

        {/* Forecast weather heatmap layer on dedicated heatmapPane (zIndex 350) */}
        <HeatLayer />

        <MapController
          routes={routes}
          origin={origin}
          destination={destination}
          isMobile={isMobile}
        />

        {/* Loading marching straight dashed line between origin and destination pins */}
        {isLoading && origin && destination && (
          <Polyline
            positions={[
              [origin.lat, origin.lon],
              [destination.lat, destination.lon],
            ]}
            pathOptions={{
              color: themeColors.primary,
              weight: 3,
              dashArray: '8, 8',
              opacity: 0.8,
            }}
          />
        )}

        {/* Alternate routes (muted, clickable) */}
        {alternateRoutes.map((alt) => {
          const coords = alt.geometry.map(([lon, lat]) => [lat, lon]);
          const midIdx = Math.floor(coords.length / 2);
          const midPoint = coords[midIdx];
          const deltaText = selectedRoute ? formatDurationDelta(alt.duration_s, selectedRoute.duration_s) : '';

          return (
            <React.Fragment key={alt.id}>
              <Polyline
                positions={coords}
                pathOptions={{
                  color: themeColors.ink3,
                  weight: 4,
                  opacity: 0.55,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
                eventHandlers={{
                  click: () => onSelectRoute(alt.id),
                }}
              />
              {midPoint && deltaText && (
                <Marker
                  position={midPoint}
                  icon={getDeltaPillIcon(deltaText)}
                  eventHandlers={{
                    click: () => onSelectRoute(alt.id),
                  }}
                />
              )}
            </React.Fragment>
          );
        })}

        {/* Selected route: 9px white casing under 6px risk-coloured stretches */}
        {selectedRoute && (
          <>
            <Polyline
              positions={casingCoords}
              pathOptions={{
                color: themeColors.white,
                weight: 9,
                opacity: 0.95,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {selectedSegments.map((seg, idx) => {
              const color = themeColors.risk[seg.level] || themeColors.risk.unknown;
              return (
                <Polyline
                  key={`${selectedRoute.id}-${seg.stretchIndex}-${idx}`}
                  positions={seg.coordinates}
                  pathOptions={{
                    color,
                    weight: 6,
                    opacity: 1.0,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
              );
            })}
          </>
        )}

        {/* Checkpoint markers on the selected route (excluding mile 0 and final mile) */}
        {visibleCheckpoints.map((cp) => {
          const levelConfig = RISK_LEVELS[cp.level] || RISK_LEVELS.unknown;
          const isHovered = activeCheckpointIndex === cp.originalIndex;
          const icon = getCheckpointIcon(cp.level, levelConfig.letter, isHovered, cp.originalIndex);
          const etaFormatted = formatLocalTime(cp.eta || cp.eta_utc);

          return (
            <Marker key={`${selectedRoute.id}-cp-${cp.originalIndex}`} position={[cp.lat, cp.lon]} icon={icon}>
              <Popup autoPan={false}>
                <div style={{ padding: '16px', minWidth: '220px' }}>
                  {/* Top badge */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span
                      style={{
                        background: themeColors.risk[cp.level] || themeColors.risk.unknown,
                        color: levelConfig.textColor,
                        fontWeight: 700,
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: 'var(--r-sm)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      {levelConfig.label}
                    </span>
                    <span style={{ fontSize: '13px', color: 'var(--ink-3)' }}>
                      Mile {cp.mile}
                    </span>
                  </div>

                  {/* ETA */}
                  <div
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '26px',
                      fontWeight: 600,
                      lineHeight: 1,
                      color: 'var(--ink)',
                      marginBottom: '12px',
                    }}
                  >
                    {etaFormatted || '--'}
                  </div>

                  {/* Weather metrics table */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '6px 12px',
                      fontSize: '13px',
                      marginBottom: '12px',
                      paddingBottom: '10px',
                      borderBottom: '1px solid var(--line)',
                    }}
                  >
                    <div>
                      <span style={{ color: 'var(--ink-3)' }}>Wind: </span>
                      <strong style={{ color: 'var(--ink)' }}>{cp.wind_mph != null ? `${Math.round(cp.wind_mph)} mph` : '--'}</strong>
                    </div>
                    {cp.gust_mph != null && (
                      <div>
                        <span style={{ color: 'var(--ink-3)' }}>Gust: </span>
                        <strong style={{ color: 'var(--ink)' }}>{Math.round(cp.gust_mph)} mph</strong>
                      </div>
                    )}
                    <div>
                      <span style={{ color: 'var(--ink-3)' }}>Rain: </span>
                      <strong style={{ color: 'var(--ink)' }}>{cp.rain_in_hr != null ? `${cp.rain_in_hr.toFixed(2)} in/h` : '--'}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--ink-3)' }}>Snow: </span>
                      <strong style={{ color: 'var(--ink)' }}>{cp.snow_in_hr != null ? `${cp.snow_in_hr.toFixed(1)} in/h` : '--'}</strong>
                    </div>
                  </div>

                  {/* Drivers / rule text */}
                  {cp.drivers && cp.drivers.length > 0 && (
                    <div style={{ fontSize: '12.5px', color: 'var(--ink-2)', lineHeight: '18px' }}>
                      {cp.drivers.join('. ')}
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Origin pin (drawn on top with zIndexOffset) */}
        {origin && (
          <Marker
            position={[origin.lat, origin.lon]}
            icon={createPinIcon('origin', origin.label || 'Origin')}
            zIndexOffset={1000}
          />
        )}

        {/* Destination pin (drawn on top with zIndexOffset) */}
        {destination && (
          <Marker
            position={[destination.lat, destination.lon]}
            icon={createPinIcon('destination', destination.label || destEtaLabel)}
            zIndexOffset={1000}
          />
        )}

        {/* Optional separate labels layer on top pane (zIndex 450) when provided */}
        {LABELS_TILE_URL ? (
          <Pane name="labels" style={{ zIndex: 450, pointerEvents: 'none' }}>
            <TileLayer
              url={LABELS_TILE_URL}
              maxZoom={12}
              eventHandlers={{ tileerror: handleTileError }}
            />
          </Pane>
        ) : null}
      </MapContainer>
    </div>
  );
}

export default React.memo(MapView);
