import { describe, it, expect } from 'vitest';
import {
  formatRouteName,
  formatReasonText,
  formatDuration,
  formatDurationDelta,
  computeRouteStretches,
  RISK_LEVELS,
} from './format';

describe('Format and Risk Mappings', () => {
  it('maps internal route IDs to Route 1, Route 2, Route 3', () => {
    expect(formatRouteName('r1')).toBe('Route 1');
    expect(formatRouteName('r2')).toBe('Route 2');
    expect(formatRouteName('r3')).toBe('Route 3');
  });

  it('translates r-prefixes inside server reason text', () => {
    const raw = 'Tied on weather risk; faster by 58 min than r2.';
    expect(formatReasonText(raw)).toBe('Tied on weather risk; faster by 58 min than Route 2.');
  });

  it('provides correct letters and colors for risk levels', () => {
    expect(RISK_LEVELS.low.letter).toBe('L');
    expect(RISK_LEVELS.moderate.letter).toBe('M');
    expect(RISK_LEVELS.high.letter).toBe('H');
    expect(RISK_LEVELS.severe.letter).toBe('S');
    expect(RISK_LEVELS.no_travel.letter).toBe('X');
    expect(RISK_LEVELS.unknown.letter).toBe('?');
  });

  it('formats duration and deltas accurately', () => {
    expect(formatDuration(3600)).toBe('1 h 0 m');
    expect(formatDuration(55200)).toBe('15 h 20 m');
    expect(formatDurationDelta(55200, 53400)).toBe('30 min slower');
    expect(formatDurationDelta(53400, 55200)).toBe('30 min faster');
  });

  it('computes route stretches with midpoint rule attribution summing to total distance', () => {
    const route = {
      distance_mi: 100,
      checkpoints: [
        { mile: 0, level: 'low' },
        { mile: 50, level: 'high' },
        { mile: 100, level: 'severe' },
      ],
    };
    const stretches = computeRouteStretches(route);
    expect(stretches).toHaveLength(3);
    // cp 0 owns [0, 25] -> 25 mi
    expect(stretches[0].miles).toBe(25);
    expect(stretches[0].level).toBe('low');
    // cp 1 owns [25, 75] -> 50 mi
    expect(stretches[1].miles).toBe(50);
    expect(stretches[1].level).toBe('high');
    // cp 2 owns [75, 100] -> 25 mi
    expect(stretches[2].miles).toBe(25);
    expect(stretches[2].level).toBe('severe');
    // Total sum
    const totalMiles = stretches.reduce((sum, s) => sum + s.miles, 0);
    expect(totalMiles).toBe(100);
  });

  it('merges adjacent stretches with the same level into one segment summing miles', async () => {
    const { computeMergedRouteStretches } = await import('./format');
    const route = {
      distance_mi: 150,
      checkpoints: [
        { mile: 0, level: 'low' },
        { mile: 30, level: 'low' },
        { mile: 60, level: 'severe' },
        { mile: 100, level: 'severe' },
        { mile: 150, level: 'low' },
      ],
    };
    const merged = computeMergedRouteStretches(route);
    // 3 segments: low (0-45), severe (45-125), low (125-150)
    expect(merged).toHaveLength(3);
    expect(merged[0].level).toBe('low');
    expect(merged[0].startMile).toBe(0);
    expect(merged[0].endMile).toBe(45);
    expect(merged[0].miles).toBe(45);

    expect(merged[1].level).toBe('severe');
    expect(merged[1].startMile).toBe(45);
    expect(merged[1].endMile).toBe(125);
    expect(merged[1].miles).toBe(80);

    expect(merged[2].level).toBe('low');
    expect(merged[2].startMile).toBe(125);
    expect(merged[2].endMile).toBe(150);
    expect(merged[2].miles).toBe(25);

    const sum = merged.reduce((acc, s) => acc + s.miles, 0);
    expect(sum).toBe(150);
  });

  it('formats average risk with formatAvgRisk correctly', async () => {
    const { formatAvgRisk } = await import('./format');
    expect(formatAvgRisk(null)).toBe('n/a');
    expect(formatAvgRisk(undefined)).toBe('n/a');
    expect(formatAvgRisk(0)).toBe('Low');
    expect(formatAvgRisk(0.04)).toBe('Low');
    expect(formatAvgRisk(0.05)).toBe('0.1');
    expect(formatAvgRisk(0.85)).toBe('0.9');
    expect(formatAvgRisk(1.24)).toBe('1.2');
    expect(formatAvgRisk(2.5)).toBe('2.5');
  });
});
