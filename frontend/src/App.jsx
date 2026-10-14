import { useState, useEffect } from 'react';
import { useTripStore } from './store/useTripStore';
import { analyze, fetchHeatmap } from './api/client';
import SearchForm from './components/SearchForm';
import RouteRows from './components/RouteRows';
import RouteSkeletons from './components/RouteSkeletons';
import MapView from './components/MapView';
import BottomSheet from './components/BottomSheet';
import { HeatmapSlider } from './components/HeatmapSlider';
import dallasDenverMock from './mocks/analyze-dallas-denver.json';
import { createMockHeatmap } from './mocks/heatmapMock';
import chicagoAtlantaMock from './mocks/analyze-chicago-atlanta.json';
import chicagoAtlantaHeatmap from './mocks/heatmap-chicago-atlanta.json';

export default function App() {
  const form = useTripStore((s) => s.form);
  const status = useTripStore((s) => s.status);
  const analysis = useTripStore((s) => s.analysis);
  const error = useTripStore((s) => s.error);
  const fieldErrors = useTripStore((s) => s.fieldErrors);
  const selectedRouteId = useTripStore((s) => s.selectedRouteId);
  const activeCheckpointIndex = useTripStore((s) => s.activeCheckpointIndex);
  const setForm = useTripStore((s) => s.setForm);
  const setStatus = useTripStore((s) => s.setStatus);
  const setAnalysis = useTripStore((s) => s.setAnalysis);
  const setError = useTripStore((s) => s.setError);
  const setSelectedRouteId = useTripStore((s) => s.setSelectedRouteId);
  const setActiveCheckpointIndex = useTripStore((s) => s.setActiveCheckpointIndex);
  const setHeatmap = useTripStore((s) => s.setHeatmap);
  const setHeatmapStatus = useTripStore((s) => s.setHeatmapStatus);

  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= 760 : false
  );
  const [sheetSnap, setSheetSnap] = useState(null);

  // Monitor resize for mobile/desktop layout
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 760);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Handle URL query parameters for dev switch: ?mock=1 and ?state=...
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mockParam = params.get('mock');
    const stateParam = params.get('state');
    const sheetParam = params.get('sheet');

    if (sheetParam) {
      setSheetSnap(sheetParam);
    }

    if (mockParam === 'heat-real') {
      setForm({
        origin: { lat: 41.8781, lon: -87.6298, label: 'Chicago, IL' },
        destination: { lat: 33.7490, lon: -84.3880, label: 'Atlanta, GA' },
        departure_time: '2026-10-14T09:36',
        load_lbs: 42000,
      });
      setAnalysis(chicagoAtlantaMock);
      setHeatmap(chicagoAtlantaHeatmap);
    } else if (mockParam === '1' || stateParam) {
      if (stateParam === 'idle') {
        setStatus('idle');
      } else if (stateParam === 'loading') {
        setStatus('loading');
      } else if (stateParam === 'error') {
        setError("Can't reach the server. Check your connection and try again.");
      } else if (stateParam === 'blocked') {
        const blockedMock = JSON.parse(JSON.stringify(dallasDenverMock));
        blockedMock.recommended_route_id = null;
        blockedMock.reason = 'All routes encounter No Travel hazards at this departure time.';
        blockedMock.routes.forEach((r) => {
          r.blocked = true;
          r.checkpoints.forEach((cp, idx) => {
            if (idx === 3 || idx === 7) {
              cp.level = 'no_travel';
              cp.drivers = ['wind 58 mph -> No Travel'];
            }
          });
        });
        setAnalysis(blockedMock);
      } else if (stateParam === 'partial') {
        const partialMock = JSON.parse(JSON.stringify(dallasDenverMock));
        partialMock.warnings = ['Weather forecast unavailable for some checkpoints; marked as Unknown.'];
        const r1 = partialMock.routes[0];
        r1.miles_by_level.unknown = 120.0;
        r1.avg_risk = null;
        r1.checkpoints.slice(2, 5).forEach((cp) => {
          cp.level = 'unknown';
          cp.score = null;
          cp.drivers = ['forecast unavailable -> Unknown'];
        });
        setAnalysis(partialMock);
      } else {
        // default mock=1 -> success
        setAnalysis(dallasDenverMock);
        setHeatmap(createMockHeatmap());
      }
    }
  }, [setForm, setAnalysis, setError, setStatus, setHeatmap]);

  // Execute route analysis
  const handleAnalyze = async () => {
    setStatus('loading');
    setHeatmapStatus('loading');
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get('mock') === '1') {
        // Mock delay to test loading skeletons
        setTimeout(() => {
          setAnalysis(dallasDenverMock);
          setHeatmap(createMockHeatmap());
        }, 500);
        return;
      }

      const payload = {
        origin: { lat: form.origin.lat, lon: form.origin.lon },
        destination: { lat: form.destination.lat, lon: form.destination.lon },
        departure_time: form.departure_time,
        load_lbs: form.load_lbs,
      };

      // Call heatmap in parallel with analyze without blocking route display
      fetchHeatmap(payload)
        .then((heatData) => {
          setHeatmap(heatData);
        })
        .catch((err) => {
          console.warn('Heatmap background fetch warning:', err);
          setHeatmapStatus('error');
        });

      const result = await analyze(payload);
      setAnalysis(result);
    } catch (err) {
      setError(err.message, err.fields || {});
    }
  };

  const isIdle = status === 'idle';
  const isLoading = status === 'loading';
  const isError = status === 'error';
  const isSuccess = status === 'success' && analysis?.routes?.length > 0;

  // Panel content component (shared between desktop panel and mobile sheet)
  const panelContent = (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        width: '100%',
      }}
    >
      {/* Brand Header */}
      <div>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '30px',
            fontWeight: 600,
            lineHeight: 1,
            margin: '0 0 6px 0',
            color: 'var(--ink)',
            letterSpacing: '0.01em',
          }}
        >
          Haulwise
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: '13px',
            lineHeight: '18px',
            color: 'var(--ink-3)',
          }}
        >
          Pick a start, a destination and when you leave. We check the forecast for the time you reach each checkpoint.
        </p>
      </div>

      {/* Form */}
      <SearchForm
        form={form}
        onChange={setForm}
        onSubmit={handleAnalyze}
        isLoading={isLoading}
        fieldErrors={fieldErrors}
        isIdle={isIdle}
      />

      {/* Divider */}
      <hr
        style={{
          border: 'none',
          borderTop: '1px solid var(--line)',
          margin: '4px 0',
        }}
      />

      {/* Skeletons on loading */}
      {isLoading && <RouteSkeletons />}

      {/* Error state with retry */}
      {isError && (
        <div
          role="alert"
          style={{
            padding: '16px',
            background: 'var(--panel)',
            borderLeft: '4px solid var(--risk-severe)',
            borderTop: '1px solid var(--line)',
            borderRight: '1px solid var(--line)',
            borderBottom: '1px solid var(--line)',
            borderRadius: 'var(--r-sm)',
          }}
        >
          <div style={{ fontSize: '14px', color: 'var(--ink)', marginBottom: '12px' }}>
            {error || "Can't reach the server. Check your connection and try again."}
          </div>
          <button
            type="button"
            onClick={handleAnalyze}
            style={{
              background: 'var(--primary)',
              color: 'var(--white)',
              border: 'none',
              borderRadius: 'var(--r-sm)',
              padding: '8px 16px',
              fontFamily: 'var(--font-ui)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      )}

      {/* Success state: Route rows */}
      {isSuccess && (
        <RouteRows
          routes={analysis.routes}
          recommendedRouteId={analysis.recommended_route_id}
          selectedRouteId={selectedRouteId}
          onSelectRoute={setSelectedRouteId}
          reason={analysis.reason}
          warnings={analysis.warnings}
          activeCheckpointIndex={activeCheckpointIndex}
          onHoverCheckpoint={setActiveCheckpointIndex}
        />
      )}
    </div>
  );

  return (
    <div
      style={{
        position: 'relative',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--ground)',
        display: 'flex',
      }}
    >
      {/* Desktop Left Docked Panel */}
      {!isMobile && (
        <aside
          style={{
            width: '420px',
            minWidth: '420px',
            height: '100%',
            overflowY: 'auto',
            background: 'var(--panel)',
            boxShadow: 'var(--panel-edge)',
            zIndex: 1000,
            padding: '24px 20px',
            position: 'relative',
          }}
        >
          {panelContent}
        </aside>
      )}

      {/* Main Map Area */}
      <main
        style={{
          flex: 1,
          height: '100%',
          position: 'relative',
        }}
      >
        <MapView
          routes={analysis?.routes || []}
          selectedRouteId={selectedRouteId}
          recommendedRouteId={analysis?.recommended_route_id}
          onSelectRoute={setSelectedRouteId}
          origin={form.origin}
          destination={form.destination}
          isLoading={isLoading}
          activeCheckpointIndex={activeCheckpointIndex}
          isMobile={isMobile}
        />
        <HeatmapSlider />
      </main>

      {/* Mobile Bottom Sheet */}
      {isMobile && (
        <BottomSheet defaultSnap={sheetSnap || (isSuccess ? 'half' : 'full')}>
          {panelContent}
        </BottomSheet>
      )}
    </div>
  );
}
