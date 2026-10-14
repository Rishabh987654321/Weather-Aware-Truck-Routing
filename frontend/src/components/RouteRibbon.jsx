import { Tooltip } from '@mui/material';
import { computeMergedRouteStretches, RISK_LEVELS } from '../utils/format';

/**
 * RouteRibbon per DESIGN_SYSTEM.md section 5 & 8 and Phase 5 Polish
 * - Merges adjacent stretches with the same risk level (summing miles)
 * - 1px gap only where level changes
 * - Tooltip showing merged mile range
 * - Checkpoint tick marks on the featured ribbon
 * - Linked hover with map markers
 */
export default function RouteRibbon({
  route,
  tall = false,
  activeCheckpointIndex = null,
  onHoverCheckpoint = () => {},
}) {
  if (!route) return null;

  const mergedStretches = computeMergedRouteStretches(route);
  const totalDistance = route.distance_mi || (route.checkpoints?.[route.checkpoints.length - 1]?.mile) || 1;
  const milesByLevel = route.miles_by_level || {};
  const summaryAria = Object.entries(milesByLevel)
    .filter(([, mi]) => mi > 0)
    .map(([lvl, mi]) => `${mi} mi ${lvl}`)
    .join(', ');

  return (
    <div
      className={`ribbon${tall ? ' ribbon--tall' : ''}`}
      role="img"
      aria-label={`Route risk breakdown: ${summaryAria || 'unknown'}`}
      style={{
        position: 'relative',
        display: 'flex',
        gap: '1px',
        height: tall ? '16px' : '12px',
        borderRadius: 'var(--r-sm)',
        overflow: 'hidden',
        background: 'var(--line)',
        width: '100%',
      }}
    >
      {mergedStretches.map((s, idx) => {
        const levelConfig = RISK_LEVELS[s.level] || RISK_LEVELS.unknown;
        const start = Math.round(s.startMile);
        const end = Math.round(s.endMile);
        const tooltipTitle = start === end
          ? `Mile ${start}, ${levelConfig.label}`
          : `Miles ${start}–${end}, ${levelConfig.label} (${Math.round(s.miles)} mi)`;

        const isHovered =
          activeCheckpointIndex !== null && s.checkpointIndices.includes(activeCheckpointIndex);

        return (
          <Tooltip key={idx} title={tooltipTitle} arrow placement="top" enterDelay={100}>
            <span
              className={`ribbon__seg level-${s.level}`}
              style={{
                flexGrow: Math.max(s.miles, 0.1),
                flexShrink: 1,
                flexBasis: 0,
                cursor: 'pointer',
                opacity: activeCheckpointIndex !== null && !isHovered ? 0.6 : 1,
                outline: isHovered ? '2px solid var(--ink)' : 'none',
                zIndex: isHovered ? 2 : 1,
                position: 'relative',
              }}
              onMouseEnter={() => onHoverCheckpoint(s.checkpointIndices[0])}
              onMouseLeave={() => onHoverCheckpoint(null)}
              tabIndex={0}
              aria-label={tooltipTitle}
            />
          </Tooltip>
        );
      })}

      {/* Checkpoint tick marks on the featured ribbon */}
      {tall && route.checkpoints && route.checkpoints.length > 2 && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            zIndex: 3,
          }}
        >
          {route.checkpoints
            .filter((cp) => cp.mile > 0 && cp.mile < totalDistance - 0.5)
            .map((cp, idx) => {
              const leftPct = (cp.mile / totalDistance) * 100;
              return (
                <div
                  key={idx}
                  style={{
                    position: 'absolute',
                    left: `${leftPct}%`,
                    top: 0,
                    bottom: 0,
                    width: '1px',
                    backgroundColor: 'rgba(255, 255, 255, 0.75)',
                    boxShadow: '0 0 1px rgba(20, 24, 27, 0.4)',
                  }}
                />
              );
            })}
        </div>
      )}
    </div>
  );
}
