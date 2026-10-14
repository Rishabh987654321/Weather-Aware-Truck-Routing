/**
 * Mock heatmap fixture for dev / ?mock=1 mode.
 * Generates a realistic moving storm band across the Dallas-to-Denver corridor
 * over 49 hours, with intensities ranging from 0.0 (calm) to 1.0 (severe / no travel).
 */
import dallasDenverMock from './analyze-dallas-denver.json';

export function createMockHeatmap() {
  const points = [];
  const coords = dallasDenverMock?.routes?.[0]?.geometry || [];
  if (!coords.length) {
    return { start_time: '2026-10-14T11:00:00Z', hours: 49, points: [] };
  }

  // Sample points along the main route plus lateral corridor swaths
  const total = coords.length;
  const numSteps = 45;
  const stepSize = Math.max(1, Math.floor(total / numSteps));

  const sampledPoints = [];
  for (let idx = 0; idx < total; idx += stepSize) {
    const [lon, lat] = coords[idx];
    const u = idx / (total - 1); // 0 (Dallas) to 1 (Denver)

    // Center point on the route
    sampledPoints.push({ lat, lon, u });

    // Lateral swath points (+/- 0.35 to 0.65 degrees) to give 2D weather footprint
    sampledPoints.push({ lat: lat + 0.32, lon: lon - 0.28, u });
    sampledPoints.push({ lat: lat - 0.28, lon: lon + 0.35, u });
    sampledPoints.push({ lat: lat + 0.55, lon: lon - 0.52, u });
  }

  // Pre-calculate 49 hours of storm intensities for each point
  for (let pIdx = 0; pIdx < sampledPoints.length; pIdx++) {
    const { lat, lon, u } = sampledPoints[pIdx];
    const intensities = [];

    for (let h = 0; h < 49; h++) {
      // Storm band center moves from Dallas (u=0) past Denver (u=1.1)
      const stormCenter = (h / 40.0) * 0.95; // at h=0 -> 0.0, h=24 -> 0.57, h=36 -> 0.855, h=48 -> 1.14
      const dist = Math.abs(u - stormCenter);

      let val = 0;
      if (h >= 47) {
        // At hour 47-48, storm has moved past the corridor, leaving calm conditions (<0.20)
        val = Math.max(0, 0.18 - dist * 0.3);
      } else if (dist < 0.09) {
        // Core severe band
        val = 0.88 + (0.09 - dist) * 1.3;
      } else if (dist < 0.20) {
        // High risk transition
        const t = (dist - 0.09) / (0.20 - 0.09);
        val = 0.85 - t * 0.30;
      } else if (dist < 0.32) {
        // Moderate risk
        const t = (dist - 0.20) / (0.32 - 0.20);
        val = 0.55 - t * 0.28;
      } else if (dist < 0.44) {
        // Low weather
        const t = (dist - 0.32) / (0.44 - 0.32);
        val = 0.27 - t * 0.17;
      } else {
        // Calm weather
        val = Math.max(0, 0.05 - (dist - 0.44) * 0.1);
      }

      // Add a tiny spatial variation so it looks organic
      const noise = Math.sin(lat * 8.0 + lon * 7.0 + h * 0.4) * 0.03;
      const finalIntensity = Math.max(0, Math.min(1.0, val + noise));
      intensities.push(Number(finalIntensity.toFixed(2)));
    }

    points.push({
      lat: Number(lat.toFixed(3)),
      lon: Number(lon.toFixed(3)),
      intensity: intensities,
    });
  }

  return {
    start_time: '2026-10-14T11:00:00Z',
    hours: 49,
    points,
  };
}
