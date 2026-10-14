import { Check, WarningCircle } from '@phosphor-icons/react';
import RouteRibbon from './RouteRibbon';
import {
  formatDuration,
  formatDurationDelta,
  formatRouteName,
  formatReasonText,
  formatAvgRisk,
} from '../utils/format';

/**
 * RouteRows per DESIGN_SYSTEM.md section 4 & 5
 */
export default function RouteRows({
  routes = [],
  recommendedRouteId = null,
  selectedRouteId = null,
  onSelectRoute = () => {},
  reason = '',
  warnings = [],
  activeCheckpointIndex = null,
  onHoverCheckpoint = () => {},
}) {
  if (!routes || routes.length === 0) return null;

  const recRoute = routes.find((r) => r.id === recommendedRouteId);
  const allBlocked = routes.every((r) => r.blocked);

  // Keyboard navigation for radiogroup
  const handleKeyDown = (e, currentIndex) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % routes.length;
      onSelectRoute(routes[nextIndex].id);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + routes.length) % routes.length;
      onSelectRoute(routes[prevIndex].id);
    }
  };

  return (
    <div
      role="radiogroup"
      aria-label="Route options"
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
      }}
    >
      {allBlocked && (
        <div
          role="alert"
          style={{
            padding: '12px 16px',
            margin: '0 0 12px 0',
            background: 'var(--panel)',
            borderLeft: '4px solid var(--risk-severe)',
            borderTop: '1px solid var(--line)',
            borderRight: '1px solid var(--line)',
            borderBottom: '1px solid var(--line)',
            borderRadius: 'var(--r-sm)',
            fontSize: '14px',
            color: 'var(--ink)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <WarningCircle size={20} color="var(--risk-severe)" weight="bold" />
          <span>No route is drivable at this departure time. Try leaving later.</span>
        </div>
      )}

      {warnings && warnings.length > 0 && (
        <div
          style={{
            padding: '10px 14px',
            margin: '0 0 12px 0',
            background: 'var(--warning-bg)',
            border: '1px solid var(--warning-line)',
            borderRadius: 'var(--r-sm)',
            fontSize: '13px',
            color: 'var(--ink-2)',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {warnings.map((w, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <WarningCircle size={16} color="var(--risk-high)" weight="bold" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: 'var(--line)' }}>
        {routes.map((route, idx) => {
          const isSelected = route.id === selectedRouteId;
          const isRecommended = route.id === recommendedRouteId;
          const displayName = formatRouteName(route.id);
          const durationStr = formatDuration(route.duration_s);
          const distanceMi = Math.round(route.distance_mi || 0);
          const avgRiskText = formatAvgRisk(route.avg_risk);
          const unknownMiles = route.miles_by_level?.unknown || 0;

          // Split duration into value and units for big display
          const durParts = durationStr.split(' '); // e.g. ["15", "h", "43", "m"]

          if (isRecommended) {
            return (
              <div
                key={route.id}
                role="radio"
                aria-checked={isSelected}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => onSelectRoute(route.id)}
                onKeyDown={(e) => handleKeyDown(e, idx)}
                style={{
                  position: 'relative',
                  padding: '16px 20px',
                  background: isSelected ? 'var(--field)' : 'var(--panel)',
                  cursor: 'pointer',
                  borderLeft: isSelected ? '3px solid var(--ink)' : '3px solid transparent',
                  outline: 'none',
                  transition: 'background var(--dur-fast) var(--ease-out)',
                }}
              >
                {/* Header: Badge & Name */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        background: 'var(--ink)',
                        color: 'var(--white)',
                        padding: '2px 8px',
                        borderRadius: 'var(--r-sm)',
                        fontSize: '12px',
                        fontWeight: 600,
                        fontFamily: 'var(--font-ui)',
                        letterSpacing: '0.01em',
                      }}
                    >
                      <Check size={13} weight="bold" />
                      Recommended
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontWeight: 600,
                        fontSize: '24px',
                        lineHeight: 1,
                        color: 'var(--ink)',
                      }}
                    >
                      {displayName}
                    </span>
                  </div>

                  {route.blocked && (
                    <span
                      style={{
                        background: 'repeating-linear-gradient(135deg, var(--risk-no-travel) 0 4px, var(--panel) 4px 8px)',
                        color: 'var(--white)',
                        padding: '3px 8px',
                        borderRadius: 'var(--r-sm)',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: 'var(--risk-no-travel)',
                      }}
                    >
                      No travel on this route
                    </span>
                  )}
                </div>

                {/* Big figures */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    gap: '20px',
                    margin: '12px 0 14px 0',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: '40px',
                        fontWeight: 600,
                        lineHeight: 1,
                        color: 'var(--ink)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {durParts[0]}
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--ink-3)' }}>
                      {durParts[1]}
                    </span>
                    {durParts[2] && (
                      <>
                        <span
                          style={{
                            fontFamily: 'var(--font-display)',
                            fontSize: '40px',
                            fontWeight: 600,
                            lineHeight: 1,
                            color: 'var(--ink)',
                            marginLeft: '4px',
                            fontVariantNumeric: 'tabular-nums',
                          }}
                        >
                          {durParts[2]}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--ink-3)' }}>
                          {durParts[3]}
                        </span>
                      </>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: '40px',
                        fontWeight: 600,
                        lineHeight: 1,
                        color: 'var(--ink)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {distanceMi}
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--ink-3)' }}>
                      mi
                    </span>
                  </div>

                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: '3px' }}>
                    <span style={{ fontSize: '12px', color: 'var(--ink-3)' }}>risk</span>
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: '22px',
                        fontWeight: 600,
                        color: 'var(--ink)',
                      }}
                    >
                      {avgRiskText}
                    </span>
                  </div>
                </div>

                {/* Tall ribbon */}
                <div style={{ marginBottom: '10px' }}>
                  <RouteRibbon
                    route={route}
                    tall
                    activeCheckpointIndex={isSelected ? activeCheckpointIndex : null}
                    onHoverCheckpoint={isSelected ? onHoverCheckpoint : () => {}}
                  />
                </div>

                {/* Reason line */}
                {reason && (
                  <p
                    style={{
                      margin: '6px 0 0 0',
                      fontSize: '14px',
                      lineHeight: '20px',
                      color: 'var(--ink-2)',
                    }}
                  >
                    {formatReasonText(reason)}
                  </p>
                )}

                {/* Unknown note */}
                {unknownMiles > 0 && (
                  <p
                    style={{
                      margin: '6px 0 0 0',
                      fontSize: '12.5px',
                      lineHeight: '16px',
                      color: 'var(--ink-3)',
                    }}
                  >
                    Forecast not available for {unknownMiles.toFixed(0)} mi. They are shown in grey and left out of the average.
                  </p>
                )}
              </div>
            );
          }

          // Compact alternate row
          const deltaText = recRoute ? formatDurationDelta(route.duration_s, recRoute.duration_s) : '';

          return (
            <div
              key={route.id}
              role="radio"
              aria-checked={isSelected}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => onSelectRoute(route.id)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              style={{
                position: 'relative',
                padding: '14px 20px',
                background: isSelected ? 'var(--field)' : 'var(--panel)',
                cursor: 'pointer',
                borderLeft: isSelected ? '3px solid var(--ink)' : '3px solid transparent',
                outline: 'none',
                transition: 'background var(--dur-fast) var(--ease-out)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  marginBottom: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                  <span
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontWeight: 600,
                      fontSize: '20px',
                      color: 'var(--ink)',
                    }}
                  >
                    {displayName}
                  </span>
                  <span
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontWeight: 600,
                      fontSize: '18px',
                      color: 'var(--ink)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {durationStr}
                  </span>
                  <span style={{ fontSize: '13px', color: 'var(--ink-3)' }}>
                    {distanceMi} mi
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {deltaText && !route.blocked && (
                    <span
                      style={{
                        fontSize: '12.5px',
                        fontWeight: 500,
                        color: 'var(--ink-3)',
                      }}
                    >
                      {deltaText}
                    </span>
                  )}
                  {route.blocked && (
                    <span
                      style={{
                        background: 'repeating-linear-gradient(135deg, var(--risk-no-travel) 0 4px, var(--panel) 4px 8px)',
                        color: 'var(--white)',
                        padding: '2px 6px',
                        borderRadius: 'var(--r-sm)',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: 'var(--risk-no-travel)',
                      }}
                    >
                      Blocked
                    </span>
                  )}
                  <span style={{ fontSize: '12px', color: 'var(--ink-3)', marginLeft: '4px' }}>
                    risk {avgRiskText}
                  </span>
                </div>
              </div>

              {/* Standard ribbon */}
              <RouteRibbon
                route={route}
                activeCheckpointIndex={isSelected ? activeCheckpointIndex : null}
                onHoverCheckpoint={isSelected ? onHoverCheckpoint : () => {}}
              />

              {unknownMiles > 0 && (
                <p
                  style={{
                    margin: '4px 0 0 0',
                    fontSize: '12px',
                    color: 'var(--ink-3)',
                  }}
                >
                  {unknownMiles.toFixed(0)} mi weather unknown
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
