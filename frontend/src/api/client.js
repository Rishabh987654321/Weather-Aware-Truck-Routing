/**
 * API client per API.md and DESIGN_SYSTEM.md section 7
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Convert local datetime-local string (e.g. "2026-10-14T08:00") to full ISO string with timezone offset
 */
export function formatLocalDepartureToISO(localDtStr) {
  if (!localDtStr) return null;
  const dt = new Date(localDtStr);
  if (isNaN(dt.getTime())) return null;
  return dt.toISOString();
}

/**
 * Geocode query via Django /api/geocode proxy
 */
export async function geocode(q, { signal } = {}) {
  if (!q || q.trim().length < 3) return [];
  const url = `${API_BASE_URL}/api/geocode?q=${encodeURIComponent(q.trim())}`;
  const response = await fetch(url, { signal });

  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    throw new Error(`Geocoding error (${response.status})`);
  }

  const data = await response.json();
  const items = Array.isArray(data)
    ? data
    : Array.isArray(data?.results)
      ? data.results
      : data && data.lat != null && data.lon != null
        ? [data]
        : [];

  return items.map((item) => ({
    lat: item.lat,
    lon: item.lon,
    label: item.label || `${item.lat.toFixed(4)}, ${item.lon.toFixed(4)}`,
  }));
}

/**
 * Format DRF errors into human-friendly strings per DESIGN_SYSTEM.md section 7
 */
export function parseApiError(status, errData) {
  if (status === 422) {
    return {
      message: 'No drivable route found between these places. Try different locations.',
      fields: {},
    };
  }

  if (status === 400 && typeof errData === 'object' && errData !== null) {
    const fields = {};
    let generalMessage = 'Please review the fields below.';

    if (errData.non_field_errors) {
      const nfe = Array.isArray(errData.non_field_errors)
        ? errData.non_field_errors.join(' ')
        : String(errData.non_field_errors);
      if (nfe.includes('same') || nfe.includes('identical')) {
        generalMessage = 'Start and destination are the same place.';
        fields.destination = 'Start and destination are the same place.';
      } else {
        generalMessage = nfe;
      }
    }

    if (errData.origin) {
      fields.origin = Array.isArray(errData.origin) ? errData.origin.join(' ') : String(errData.origin);
    }
    if (errData.destination) {
      fields.destination = Array.isArray(errData.destination)
        ? errData.destination.join(' ')
        : String(errData.destination);
    }
    if (errData.departure_time) {
      const depMsg = Array.isArray(errData.departure_time)
        ? errData.departure_time.join(' ')
        : String(errData.departure_time);
      fields.departure_time = depMsg;
      generalMessage = depMsg;
    }
    if (errData.load_lbs) {
      const loadMsg = 'Enter a load above 0 lb.';
      fields.load_lbs = loadMsg;
      generalMessage = loadMsg;
    }

    return { message: generalMessage, fields };
  }

  if (status >= 500) {
    return {
      message: "Can't reach the server. Check your connection and try again.",
      fields: {},
    };
  }

  const raw = errData?.detail || errData?.message || "Can't reach the server. Check your connection and try again.";
  return { message: raw, fields: {} };
}

/**
 * Call /api/analyze
 */
export async function analyze(payload) {
  // Ensure departure_time is ISO with UTC offset
  const formattedPayload = {
    ...payload,
    departure_time: payload.departure_time.includes('Z') || payload.departure_time.includes('+')
      ? payload.departure_time
      : formatLocalDepartureToISO(payload.departure_time),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formattedPayload),
    });

    const data = await response.json();

    if (!response.ok) {
      const parsed = parseApiError(response.status, data);
      const err = new Error(parsed.message);
      err.status = response.status;
      err.fields = parsed.fields;
      throw err;
    }

    return data;
  } catch (err) {
    if (err.status) throw err;
    const netErr = new Error("Can't reach the server. Check your connection and try again.");
    netErr.status = 0;
    netErr.fields = {};
    throw netErr;
  }
}

export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

/**
 * Call /api/heatmap
 */
export async function fetchHeatmap(payload) {
  const formattedPayload = {
    ...payload,
    departure_time:
      payload.departure_time &&
      (payload.departure_time.includes('Z') || payload.departure_time.includes('+'))
        ? payload.departure_time
        : formatLocalDepartureToISO(payload.departure_time),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/api/heatmap`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formattedPayload),
    });

    const data = await response.json();

    if (!response.ok) {
      const parsed = parseApiError(response.status, data);
      const err = new Error(parsed.message);
      err.status = response.status;
      err.fields = parsed.fields;
      throw err;
    }

    return data;
  } catch (err) {
    if (err.status) throw err;
    const netErr = new Error("Can't reach the server. Check your connection and try again.");
    netErr.status = 0;
    netErr.fields = {};
    throw netErr;
  }
}

