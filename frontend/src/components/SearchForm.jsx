import { useState, useEffect, useRef } from 'react';
import { ArrowsDownUp, Circle, Square, Spinner, Info } from '@phosphor-icons/react';
import { Tooltip } from '@mui/material';
import { geocode } from '../api/client';

const EXAMPLE_TRIPS = [
  {
    label: 'Dallas to Denver',
    origin: { lat: 32.7767, lon: -96.7970, label: 'Dallas, TX' },
    destination: { lat: 39.7392, lon: -104.9903, label: 'Denver, CO' },
    load_lbs: 42000,
  },
  {
    label: 'Chicago to Atlanta',
    origin: { lat: 41.8781, lon: -87.6298, label: 'Chicago, IL' },
    destination: { lat: 33.7490, lon: -84.3880, label: 'Atlanta, GA' },
    load_lbs: 35000,
  },
  {
    label: 'Cheyenne to Rock Springs',
    origin: { lat: 41.1400, lon: -104.8202, label: 'Cheyenne, WY' },
    destination: { lat: 41.5875, lon: -109.2029, label: 'Rock Springs, WY' },
    load_lbs: 28000,
    hint: 'Often windy',
  },
];

// In-memory query cache for geocode
const geocodeCache = new Map();

export default function SearchForm({
  form,
  onChange,
  onSubmit,
  isLoading = false,
  fieldErrors = {},
  isIdle = true,
}) {
  const [originQuery, setOriginQuery] = useState(form.origin?.label || '');
  const [destQuery, setDestQuery] = useState(form.destination?.label || '');
  const [originOptions, setOriginOptions] = useState([]);
  const [destOptions, setDestOptions] = useState([]);
  const [isSearchingOrigin, setIsSearchingOrigin] = useState(false);
  const [isSearchingDest, setIsSearchingDest] = useState(false);
  const [showOriginMenu, setShowOriginMenu] = useState(false);
  const [showDestMenu, setShowDestMenu] = useState(false);

  const originAbortRef = useRef(null);
  const destAbortRef = useRef(null);

  // Sync internal input string when form values change externally (e.g. example chips)
  useEffect(() => {
    if (form.origin?.label) setOriginQuery(form.origin.label);
  }, [form.origin]);

  useEffect(() => {
    if (form.destination?.label) setDestQuery(form.destination.label);
  }, [form.destination]);

  // Debounced geocode search for Origin
  useEffect(() => {
    if (!originQuery || originQuery.trim().length < 3 || form.origin?.label === originQuery) {
      setOriginOptions([]);
      setIsSearchingOrigin(false);
      return;
    }

    const trimmed = originQuery.trim().toLowerCase();
    if (geocodeCache.has(trimmed)) {
      setOriginOptions(geocodeCache.get(trimmed));
      setShowOriginMenu(true);
      return;
    }

    setIsSearchingOrigin(true);
    if (originAbortRef.current) originAbortRef.current.abort();
    const abortCtrl = new AbortController();
    originAbortRef.current = abortCtrl;

    const timer = setTimeout(async () => {
      try {
        const results = await geocode(trimmed, { signal: abortCtrl.signal });
        geocodeCache.set(trimmed, results);
        setOriginOptions(results);
        setShowOriginMenu(true);
      } catch (err) {
        if (err.name !== 'AbortError') setOriginOptions([]);
      } finally {
        setIsSearchingOrigin(false);
      }
    }, 600);

    return () => {
      clearTimeout(timer);
      abortCtrl.abort();
    };
  }, [originQuery, form.origin]);

  // Debounced geocode search for Destination
  useEffect(() => {
    if (!destQuery || destQuery.trim().length < 3 || form.destination?.label === destQuery) {
      setDestOptions([]);
      setIsSearchingDest(false);
      return;
    }

    const trimmed = destQuery.trim().toLowerCase();
    if (geocodeCache.has(trimmed)) {
      setDestOptions(geocodeCache.get(trimmed));
      setShowDestMenu(true);
      return;
    }

    setIsSearchingDest(true);
    if (destAbortRef.current) destAbortRef.current.abort();
    const abortCtrl = new AbortController();
    destAbortRef.current = abortCtrl;

    const timer = setTimeout(async () => {
      try {
        const results = await geocode(trimmed, { signal: abortCtrl.signal });
        geocodeCache.set(trimmed, results);
        setDestOptions(results);
        setShowDestMenu(true);
      } catch (err) {
        if (err.name !== 'AbortError') setDestOptions([]);
      } finally {
        setIsSearchingDest(false);
      }
    }, 600);

    return () => {
      clearTimeout(timer);
      abortCtrl.abort();
    };
  }, [destQuery, form.destination]);

  // Swap origin and destination
  const handleSwap = () => {
    const tempO = form.origin;
    const tempD = form.destination;
    onChange({
      ...form,
      origin: tempD,
      destination: tempO,
    });
  };

  // Local browser timezone abbreviation
  const tzAbbr = (() => {
    try {
      const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(new Date());
      const tzPart = parts.find((p) => p.type === 'timeZoneName');
      if (tzPart?.value) return tzPart.value;
      const str = new Date().toLocaleTimeString([], { timeZoneName: 'short' }).split(' ');
      return str[str.length - 1] || 'UTC';
    } catch {
      return 'UTC';
    }
  })();

  const isValid =
    form.origin &&
    form.destination &&
    form.origin.lat != null &&
    form.destination.lat != null &&
    (form.origin.lat !== form.destination.lat || form.origin.lon !== form.destination.lon) &&
    form.load_lbs > 0 &&
    Boolean(form.departure_time);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (isValid && !isLoading) onSubmit();
      }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        width: '100%',
      }}
    >
      {/* Origin / Destination Spine */}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          padding: '10px 0',
        }}
      >
        {/* Spine Graphic Line */}
        <div
          style={{
            position: 'absolute',
            left: '17px',
            top: '26px',
            bottom: '26px',
            width: '2px',
            borderLeft: '2px dotted var(--ink-3)',
            zIndex: 1,
            pointerEvents: 'none',
          }}
        />

        {/* Origin field */}
        <div style={{ position: 'relative', zIndex: showOriginMenu ? 50 : 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0,
              }}
            >
              <Circle size={14} weight="bold" color="var(--primary)" />
            </div>

            <div style={{ flex: 1, position: 'relative' }}>
              <input
                id="origin-input"
                type="text"
                value={originQuery}
                onChange={(e) => {
                  setOriginQuery(e.target.value);
                  if (form.origin) onChange({ ...form, origin: null });
                }}
                onFocus={() => {
                  if (originOptions.length > 0) setShowOriginMenu(true);
                }}
                placeholder="Start location (city or coordinates)"
                autoComplete="off"
                style={{
                  width: '100%',
                  height: '44px',
                  padding: '0 36px 0 12px',
                  background: 'var(--field)',
                  border: `1px solid ${fieldErrors.origin ? 'var(--risk-severe)' : 'var(--line)'}`,
                  borderRadius: 'var(--r-sm)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '14px',
                  color: 'var(--ink)',
                  outline: 'none',
                }}
              />
              {isSearchingOrigin && (
                <div style={{ position: 'absolute', right: '12px', top: '14px' }}>
                  <Spinner size={16} className="spin-icon" color="var(--ink-3)" />
                </div>
              )}

              {/* Autocomplete dropdown */}
              {showOriginMenu && originOptions.length > 0 && (
                <ul
                  style={{
                    position: 'absolute',
                    top: '48px',
                    left: 0,
                    right: 0,
                    maxHeight: '200px',
                    overflowY: 'auto',
                    background: 'var(--field)',
                    backgroundColor: 'var(--field)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--r-sm)',
                    boxShadow: '0 8px 24px rgba(20,24,27,0.22)',
                    zIndex: 1000,
                    margin: 0,
                    padding: '4px 0',
                    listStyle: 'none',
                  }}
                >
                  {originOptions.map((opt, i) => (
                    <li
                      key={i}
                      onMouseDown={() => {
                        onChange({ ...form, origin: opt });
                        setOriginQuery(opt.label);
                        setShowOriginMenu(false);
                      }}
                      style={{
                        padding: '10px 14px',
                        fontSize: '13px',
                        cursor: 'pointer',
                        color: 'var(--ink)',
                        backgroundColor: 'var(--field)',
                        borderBottom: i < originOptions.length - 1 ? '1px solid var(--line)' : 'none',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--ground)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--field)';
                      }}
                    >
                      {opt.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Swap button */}
            <button
              type="button"
              onClick={handleSwap}
              aria-label="Swap start and destination"
              style={{
                width: '36px',
                height: '36px',
                display: 'grid',
                placeItems: 'center',
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: 'var(--r-sm)',
                cursor: 'pointer',
                color: 'var(--ink-2)',
                transition: 'transform var(--dur-base) var(--ease-out)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--ink-3)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--line)';
              }}
            >
              <ArrowsDownUp size={16} weight="bold" />
            </button>
          </div>

          {fieldErrors.origin && (
            <div style={{ fontSize: '12px', color: 'var(--risk-severe)', marginLeft: '46px', marginTop: '4px' }}>
              {fieldErrors.origin}
            </div>
          )}
        </div>

        {/* Destination field */}
        <div style={{ position: 'relative', zIndex: showDestMenu ? 50 : 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0,
              }}
            >
              <Square size={13} weight="bold" color="var(--ink)" />
            </div>

            <div style={{ flex: 1, position: 'relative' }}>
              <input
                id="destination-input"
                type="text"
                value={destQuery}
                onChange={(e) => {
                  setDestQuery(e.target.value);
                  if (form.destination) onChange({ ...form, destination: null });
                }}
                onFocus={() => {
                  if (destOptions.length > 0) setShowDestMenu(true);
                }}
                placeholder="Destination location (city or coordinates)"
                autoComplete="off"
                style={{
                  width: '100%',
                  height: '44px',
                  padding: '0 36px 0 12px',
                  background: 'var(--field)',
                  border: `1px solid ${fieldErrors.destination ? 'var(--risk-severe)' : 'var(--line)'}`,
                  borderRadius: 'var(--r-sm)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '14px',
                  color: 'var(--ink)',
                  outline: 'none',
                }}
              />
              {isSearchingDest && (
                <div style={{ position: 'absolute', right: '12px', top: '14px' }}>
                  <Spinner size={16} className="spin-icon" color="var(--ink-3)" />
                </div>
              )}

              {/* Autocomplete dropdown */}
              {showDestMenu && destOptions.length > 0 && (
                <ul
                  style={{
                    position: 'absolute',
                    top: '48px',
                    left: 0,
                    right: 0,
                    maxHeight: '200px',
                    overflowY: 'auto',
                    background: 'var(--field)',
                    backgroundColor: 'var(--field)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--r-sm)',
                    boxShadow: '0 8px 24px rgba(20,24,27,0.22)',
                    zIndex: 1000,
                    margin: 0,
                    padding: '4px 0',
                    listStyle: 'none',
                  }}
                >
                  {destOptions.map((opt, i) => (
                    <li
                      key={i}
                      onMouseDown={() => {
                        onChange({ ...form, destination: opt });
                        setDestQuery(opt.label);
                        setShowDestMenu(false);
                      }}
                      style={{
                        padding: '10px 14px',
                        fontSize: '13px',
                        cursor: 'pointer',
                        color: 'var(--ink)',
                        backgroundColor: 'var(--field)',
                        borderBottom: i < destOptions.length - 1 ? '1px solid var(--line)' : 'none',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--ground)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--field)';
                      }}
                    >
                      {opt.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Spacer to balance swap button */}
            <div style={{ width: '36px' }} />
          </div>

          {fieldErrors.destination && (
            <div style={{ fontSize: '12px', color: 'var(--risk-severe)', marginLeft: '46px', marginTop: '4px' }}>
              {fieldErrors.destination}
            </div>
          )}
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', marginLeft: '46px', marginTop: '2px' }}>
            US locations only
          </div>
        </div>
      </div>

      {/* Departure & Load inputs */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '12px' }}>
        {/* Departure */}
        <div>
          <label
            htmlFor="departure-input"
            style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)', marginBottom: '4px' }}
          >
            Leave
          </label>
          <input
            id="departure-input"
            type="datetime-local"
            value={form.departure_time}
            onChange={(e) => onChange({ ...form, departure_time: e.target.value })}
            style={{
              width: '100%',
              height: '44px',
              padding: '0 8px',
              background: 'var(--field)',
              border: `1px solid ${fieldErrors.departure_time ? 'var(--risk-severe)' : 'var(--line)'}`,
              borderRadius: 'var(--r-sm)',
              fontFamily: 'var(--font-ui)',
              fontSize: '13px',
              color: 'var(--ink)',
              outline: 'none',
            }}
          />
          <div style={{ fontSize: '11px', color: 'var(--ink-3)', marginTop: '4px' }}>
            Shown in your time zone ({tzAbbr})
          </div>
          {fieldErrors.departure_time && (
            <div style={{ fontSize: '11px', color: 'var(--risk-severe)', marginTop: '2px' }}>
              {fieldErrors.departure_time}
            </div>
          )}
        </div>

        {/* Load */}
        <div>
          <label
            htmlFor="load-input"
            style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--ink-2)', marginBottom: '4px' }}
          >
            Load
          </label>
          <div style={{ position: 'relative' }}>
            <input
              id="load-input"
              type="number"
              min="1"
              step="1000"
              value={form.load_lbs}
              onChange={(e) => onChange({ ...form, load_lbs: parseInt(e.target.value, 10) || 0 })}
              style={{
                width: '100%',
                height: '44px',
                padding: '0 30px 0 10px',
                background: 'var(--field)',
                border: `1px solid ${fieldErrors.load_lbs ? 'var(--risk-severe)' : 'var(--line)'}`,
                borderRadius: 'var(--r-sm)',
                fontFamily: 'var(--font-ui)',
                fontSize: '14px',
                color: 'var(--ink)',
                outline: 'none',
              }}
            />
            <span
              style={{
                position: 'absolute',
                right: '10px',
                top: '13px',
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--ink-3)',
                pointerEvents: 'none',
              }}
            >
              lb
            </span>
          </div>
          {fieldErrors.load_lbs && (
            <div style={{ fontSize: '11px', color: 'var(--risk-severe)', marginTop: '2px' }}>
              {fieldErrors.load_lbs}
            </div>
          )}
        </div>
      </div>

      <div style={{ fontSize: '11.5px', color: 'var(--ink-3)', marginTop: '-6px' }}>
        Over 30,000 lb is stricter in high wind.
      </div>

      {/* Main Action Button */}
      <div style={{ position: 'relative', marginTop: '4px' }}>
        <button
          type="submit"
          disabled={!isValid || isLoading}
          onClick={() => {
            if (isValid && !isLoading) onSubmit();
          }}
          style={{
            width: '100%',
            height: '48px',
            background: isValid && !isLoading ? 'var(--primary)' : 'var(--risk-unknown)',
            color: 'var(--white)',
            border: 'none',
            borderRadius: 'var(--r-md)',
            fontFamily: 'var(--font-ui)',
            fontSize: '15px',
            fontWeight: 600,
            cursor: isValid && !isLoading ? 'pointer' : 'not-allowed',
            transition: 'background var(--dur-fast) var(--ease-out), transform 80ms',
            position: 'relative',
            overflow: 'hidden',
          }}
          onMouseDown={(e) => {
            if (isValid && !isLoading) e.currentTarget.style.transform = 'scale(0.98)';
          }}
          onMouseUp={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          {isLoading ? 'Checking routes and forecasts...' : 'Find safest route'}
          {isLoading && (
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: '3px',
                background: 'rgba(255, 255, 255, 0.4)',
              }}
            >
              <div
                className="skeleton"
                style={{
                  width: '100%',
                  height: '100%',
                  background: 'var(--white)',
                }}
              />
            </div>
          )}
        </button>
      </div>

      {/* Idle example chips */}
      {isIdle && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink-3)', marginBottom: '6px' }}>
            Try an example route:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {EXAMPLE_TRIPS.map((trip, idx) => (
              <Tooltip key={idx} title={trip.hint || ''} arrow placement="bottom">
                <button
                  type="button"
                  onClick={() => {
                    onChange({
                      ...form,
                      origin: trip.origin,
                      destination: trip.destination,
                      load_lbs: trip.load_lbs,
                    });
                    setOriginQuery(trip.origin.label);
                    setDestQuery(trip.destination.label);
                  }}
                  style={{
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    borderRadius: 'var(--r-sm)',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontFamily: 'var(--font-ui)',
                    color: 'var(--ink)',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--ink-2)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--line)';
                  }}
                >
                  <span>{trip.label}</span>
                  {trip.hint && <Info size={12} color="var(--ink-3)" />}
                </button>
              </Tooltip>
            ))}
          </div>
        </div>
      )}
    </form>
  );
}
