/**
 * Geometry helpers for client-side polyline stretching
 */

export function haversineDistanceMi(lat1, lon1, lat2, lon2) {
  const R = 3958.8; // Earth radius in miles
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Split route geometry [[lon, lat], ...] into risk segments matching checkpoint ownership stretches
 */
export function segmentRouteGeometry(route, stretches) {
  if (!route || !route.geometry || route.geometry.length < 2 || !stretches || stretches.length === 0) {
    return [];
  }

  const coords = route.geometry.map(([lon, lat]) => [lat, lon]);
  const n = coords.length;

  // Compute raw cumulative haversine distance
  const cumRaw = [0];
  for (let i = 1; i < n; i++) {
    const d = haversineDistanceMi(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]);
    cumRaw.push(cumRaw[i - 1] + d);
  }

  const totalRaw = cumRaw[n - 1] || 1;
  const targetDist = route.distance_mi || totalRaw;
  const scale = targetDist / totalRaw;

  // Scale cumulative miles
  const cumMiles = cumRaw.map((d) => d * scale);

  // Divide coords into slices for each stretch
  const segments = [];
  let ptIdx = 0;

  for (let sIdx = 0; sIdx < stretches.length; sIdx++) {
    const s = stretches[sIdx];
    const segCoords = [];

    // Include the point from previous stretch to ensure continuous line
    if (ptIdx > 0 && ptIdx < n) {
      segCoords.push(coords[ptIdx - 1]);
    }

    while (ptIdx < n && cumMiles[ptIdx] <= s.endMile) {
      segCoords.push(coords[ptIdx]);
      ptIdx++;
    }

    // Always ensure at least 2 points for a valid polyline
    if (segCoords.length < 2 && ptIdx < n) {
      segCoords.push(coords[ptIdx]);
    }

    segments.push({
      stretchIndex: s.index,
      level: s.level,
      checkpoint: s.checkpoint,
      coordinates: segCoords.length >= 2 ? segCoords : coords.slice(0, 2),
    });
  }

  return segments;
}
