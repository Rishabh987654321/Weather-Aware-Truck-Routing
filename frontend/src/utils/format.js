/**
 * Formatters and converters per DESIGN_SYSTEM.md and RULES.md
 */

export const RISK_LEVELS = {
  low: { letter: 'L', label: 'Low', textColor: 'var(--ink)' },
  moderate: { letter: 'M', label: 'Moderate', textColor: 'var(--ink)' },
  high: { letter: 'H', label: 'High', textColor: 'var(--ink)' },
  severe: { letter: 'S', label: 'Severe', textColor: 'var(--white)' },
  no_travel: { letter: 'X', label: 'No Travel', textColor: 'var(--white)' },
  unknown: { letter: '?', label: 'Unknown', textColor: 'var(--ink)' },
};

/**
 * Format seconds to "X h Y m"
 */
export function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '0 m';
  const totalMin = Math.round(seconds / 60);
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours === 0) return `${mins} m`;
  return `${hours} h ${mins} m`;
}

/**
 * Format duration delta between route and recommended route
 */
export function formatDurationDelta(routeDuration, recDuration) {
  if (routeDuration == null || recDuration == null) return '';
  const diffSec = routeDuration - recDuration;
  const diffMin = Math.round(diffSec / 60);
  if (diffMin > 0) return `${diffMin} min slower`;
  if (diffMin < 0) return `${Math.abs(diffMin)} min faster`;
  return 'Same time';
}

/**
 * Replace internal route IDs like "r1", "r2", "r3" with "Route 1", "Route 2", "Route 3"
 */
export function formatRouteName(id) {
  if (!id) return '';
  const match = id.match(/^r(\d+)$/i);
  if (match) {
    return `Route ${match[1]}`;
  }
  return id;
}

/**
 * Clean up server reason strings replacing r1, r2, r3 with Route 1, Route 2, Route 3
 */
export function formatReasonText(reason) {
  if (!reason) return '';
  return reason.replace(/\br(\d+)\b/gi, 'Route $1');
}

/**
 * Format date time to local time with timezone abbreviation (e.g. "8:57 AM CDT")
 */
export function formatLocalTime(isoString) {
  if (!isoString) return '';
  try {
    const dt = new Date(isoString);
    const timeStr = dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    // Extract short timezone abbreviation
    const tzMatch = dt.toLocaleTimeString([], { timeZoneName: 'short' }).split(' ');
    const tz = tzMatch[tzMatch.length - 1] || '';
    return `${timeStr} ${tz}`.trim();
  } catch {
    return isoString;
  }
}

/**
 * Format date for departure display, e.g. "Tue 14 Oct 6:00 AM"
 */
export function formatDepartureSummary(isoString) {
  if (!isoString) return '';
  try {
    const dt = new Date(isoString);
    const dateStr = dt.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' });
    const timeStr = dt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    return `${dateStr} ${timeStr}`;
  } catch {
    return isoString;
  }
}

/**
 * Calculate stretches for the ribbon using the midpoint rule (RULES.md A4)
 * Returns array of stretches: [{ checkpointIndex, level, miles, startMile, endMile, etaLocal, ... }]
 */
export function computeRouteStretches(route) {
  if (!route || !route.checkpoints || route.checkpoints.length === 0) {
    return [];
  }
  const cps = route.checkpoints;
  const n = cps.length;
  const totalDistance = route.distance_mi || cps[n - 1].mile || 1;

  if (n === 1) {
    return [{
      index: 0,
      level: cps[0].level || 'unknown',
      miles: totalDistance,
      startMile: 0,
      endMile: totalDistance,
      checkpoint: cps[0],
    }];
  }

  const boundaries = [0];
  for (let i = 0; i < n - 1; i++) {
    const mid = (cps[i].mile + cps[i + 1].mile) / 2;
    boundaries.push(mid);
  }
  boundaries.push(totalDistance);

  const stretches = [];
  for (let i = 0; i < n; i++) {
    const start = boundaries[i];
    const end = boundaries[i + 1];
    const miles = Math.max(0, end - start);
    stretches.push({
      index: i,
      level: cps[i].level || 'unknown',
      miles: parseFloat(miles.toFixed(2)),
      startMile: parseFloat(start.toFixed(1)),
      endMile: parseFloat(end.toFixed(1)),
      checkpoint: cps[i],
    });
  }

  return stretches;
}

/**
 * Format average risk: one decimal only when above 0; "Low" when it rounds to 0.
 */
export function formatAvgRisk(avgRisk) {
  if (avgRisk == null || isNaN(avgRisk)) return 'n/a';
  const val = Number(avgRisk);
  const rounded = Math.round(val * 10) / 10;
  if (rounded <= 0) {
    return 'Low';
  }
  return rounded.toFixed(1);
}

/**
 * Merge adjacent stretches of the same risk level into one segment.
 * Returns: [{ level, miles, startMile, endMile, checkpointIndices, checkpoints }]
 */
export function computeMergedRouteStretches(route) {
  const stretches = computeRouteStretches(route);
  if (!stretches.length) return [];

  const merged = [];
  let current = null;

  for (const s of stretches) {
    if (!current || current.level !== s.level) {
      if (current) merged.push(current);
      current = {
        level: s.level,
        miles: s.miles,
        startMile: s.startMile,
        endMile: s.endMile,
        checkpointIndices: [s.index],
        checkpoints: [s.checkpoint],
      };
    } else {
      current.miles = parseFloat((current.miles + s.miles).toFixed(2));
      current.endMile = s.endMile;
      current.checkpointIndices.push(s.index);
      current.checkpoints.push(s.checkpoint);
    }
  }
  if (current) merged.push(current);

  return merged;
}

/**
 * Format forecast timestamp and hour offset for display.
 */
export function formatForecastTime(startTimeStr, hourOffset) {
  if (!startTimeStr) {
    return {
      plusHours: `+${hourOffset}h`,
      formattedTime: '',
      fullLabel: `+${hourOffset}h`,
    };
  }

  const baseDate = new Date(startTimeStr);
  if (isNaN(baseDate.getTime())) {
    return {
      plusHours: `+${hourOffset}h`,
      formattedTime: '',
      fullLabel: `+${hourOffset}h`,
    };
  }

  const targetDate = new Date(baseDate.getTime() + hourOffset * 3600 * 1000);
  const weekday = targetDate.toLocaleDateString(undefined, { weekday: 'short' });
  const timeStr = targetDate.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });

  return {
    plusHours: `+${hourOffset}h`,
    formattedTime: `${weekday} ${timeStr}`,
    fullLabel: `+${hourOffset}h · ${weekday} ${timeStr}`,
  };
}

/**
 * Filter out checkpoint markers at mile 0 or at the final mile
 */
export function filterVisibleCheckpoints(checkpoints, distanceMi = 0) {
  if (!checkpoints?.length) return [];
  const lastIdx = checkpoints.length - 1;
  const maxMile = distanceMi || (checkpoints[lastIdx]?.mile ?? 0);
  return checkpoints
    .map((cp, originalIndex) => ({ ...cp, originalIndex }))
    .filter((cp, idx) => {
      if (idx === 0 || cp.mile === 0) return false;
      if (idx === lastIdx || Math.abs(cp.mile - maxMile) < 0.5) return false;
      return true;
    });
}
