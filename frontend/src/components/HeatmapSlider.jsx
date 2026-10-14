import { useEffect, useMemo, useRef } from 'react';
import { Play, Pause, Eye, EyeSlash } from '@phosphor-icons/react';
import { useTripStore } from '../store/useTripStore';
import { formatForecastTime } from '../utils/format';

export function HeatmapSlider() {
  const heatmap = useTripStore((s) => s.heatmap);
  const heatmapStatus = useTripStore((s) => s.heatmapStatus);
  const heatHour = useTripStore((s) => s.heatHour);
  const showHeatmap = useTripStore((s) => s.showHeatmap);
  const isPlaying = useTripStore((s) => s.isPlaying);

  const setHeatHour = useTripStore((s) => s.setHeatHour);
  const setShowHeatmap = useTripStore((s) => s.setShowHeatmap);
  const setIsPlaying = useTripStore((s) => s.setIsPlaying);

  const timerRef = useRef(null);

  // Auto-play timer effect (400ms per step per DESIGN_SYSTEM.md section 11)
  useEffect(() => {
    if (isPlaying && showHeatmap) {
      timerRef.current = setInterval(() => {
        setHeatHour((curr) => (curr >= 48 ? 0 : curr + 1));
      }, 400);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isPlaying, showHeatmap, setHeatHour]);

  const startTime = heatmap?.start_time || new Date().toISOString();
  const currentHour = typeof heatHour === 'number' && !isNaN(heatHour) ? heatHour : 0;
  const timeInfo = formatForecastTime(startTime, currentHour);

  // O(1) lookup of precomputed per-hour maximum intensity
  const maxIntensity = useMemo(() => {
    if (heatmap?.maxByHour) {
      return heatmap.maxByHour[currentHour] || 0;
    }
    if (!heatmap?.points?.length) return 0;
    let max = 0;
    const pts = heatmap.points;
    for (let i = 0; i < pts.length; i++) {
      const val = pts[i].intensity?.[currentHour] || 0;
      if (val > max) max = val;
    }
    return max;
  }, [heatmap, currentHour]);

  const isCalm = maxIntensity < 0.25;

  // If heatmap is not active or not yet requested, hide bottom bar
  if (heatmapStatus === 'idle' && !heatmap) {
    return null;
  }

  const handleSliderChange = (e) => {
    if (!showHeatmap) return;
    if (isPlaying) setIsPlaying(false);
    setHeatHour(Number(e.target.value));
  };

  const togglePlay = () => {
    if (!showHeatmap) return;
    setIsPlaying(!isPlaying);
  };

  const toggleLayer = () => {
    const nextShow = !showHeatmap;
    setShowHeatmap(nextShow);
    if (!nextShow && isPlaying) {
      setIsPlaying(false);
    }
  };

  return (
    <div className="bottom-control-bar" role="region" aria-label="Forecast heatmap timeline controls">
      {/* Top row: Label, Time, Loading State, Toggle */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              fontSize: '15px',
              color: 'var(--ink)',
              letterSpacing: '0.02em',
            }}
          >
            Forecast heatmap
          </span>

          {heatmapStatus === 'loading' ? (
            <span
              style={{
                fontSize: '12px',
                color: 'var(--ink-3)',
                background: 'var(--ground)',
                padding: '2px 8px',
                borderRadius: 'var(--r-sm)',
              }}
            >
              Loading forecasts...
            </span>
          ) : (
            <span
              style={{
                display: 'inline-block',
                minWidth: '130px',
                fontFamily: 'var(--font-display)',
                fontWeight: 600,
                fontSize: '17px',
                color: showHeatmap ? 'var(--primary)' : 'var(--ink-3)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {timeInfo.plusHours}{' '}
              <span style={{ fontSize: '13px', color: 'var(--ink-2)', fontWeight: 500 }}>
                {timeInfo.formattedTime ? `· ${timeInfo.formattedTime}` : ''}
              </span>
            </span>
          )}

          {/* Calm corridor note */}
          {showHeatmap && isCalm && (
            <span
              style={{
                fontSize: '12px',
                fontFamily: 'var(--font-ui)',
                color: 'var(--ink-3)',
                background: 'var(--field)',
                border: '1px solid var(--line)',
                padding: '2px 8px',
                borderRadius: 'var(--r-sm)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                animation: 'fade-in var(--dur-base) var(--ease-out)',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: 'var(--risk-low)',
                  display: 'inline-block',
                }}
              />
              Forecast is calm along this corridor at this hour.
            </span>
          )}
        </div>

        {/* Right side: Legend and Layer Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Legend gradient strip (dimmed when heatmap is off) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              color: 'var(--ink-3)',
              fontFamily: 'var(--font-ui)',
              opacity: showHeatmap ? 1 : 0.35,
              transition: 'opacity var(--dur-base) var(--ease-out)',
              pointerEvents: 'none',
            }}
          >
            <span>Low</span>
            <div className="heat-legend-bar" title="Risk: Low to No Travel" />
            <span>No Travel</span>
          </div>

          {/* Toggle Layer Visibility */}
          <button
            type="button"
            className="play-toggle-btn"
            onClick={toggleLayer}
            aria-pressed={showHeatmap}
            title={showHeatmap ? 'Hide forecast heatmap' : 'Show forecast heatmap'}
            style={{
              borderColor: showHeatmap ? 'var(--line)' : 'var(--risk-unknown)',
              opacity: showHeatmap ? 1 : 0.65,
            }}
          >
            {showHeatmap ? (
              <>
                <Eye size={16} weight="bold" />
                <span>On</span>
              </>
            ) : (
              <>
                <EyeSlash size={16} weight="bold" />
                <span>Off</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Bottom row: Play Button + Slider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <button
          type="button"
          className="play-toggle-btn"
          onClick={togglePlay}
          disabled={!showHeatmap}
          aria-label={isPlaying ? 'Pause forecast timeline' : 'Play forecast timeline'}
          title={!showHeatmap ? 'Heatmap is off' : isPlaying ? 'Pause' : 'Play timeline animation'}
          style={{
            minWidth: '78px',
            opacity: showHeatmap ? 1 : 0.4,
            cursor: showHeatmap ? 'pointer' : 'not-allowed',
          }}
        >
          {isPlaying ? (
            <>
              <Pause size={15} weight="fill" />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play size={15} weight="fill" />
              <span>Play</span>
            </>
          )}
        </button>

        <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
          <input
            type="range"
            min="0"
            max="48"
            step="1"
            value={currentHour}
            onChange={handleSliderChange}
            disabled={!showHeatmap}
            className="heat-slider"
            aria-label="Forecast hour slider"
            aria-valuemin="0"
            aria-valuemax="48"
            aria-valuenow={currentHour}
            aria-valuetext={timeInfo.fullLabel}
            style={{
              opacity: showHeatmap ? 1 : 0.4,
              cursor: showHeatmap ? 'pointer' : 'not-allowed',
              background: showHeatmap
                ? `linear-gradient(90deg, var(--ink) ${(currentHour / 48) * 100}%, var(--line) ${(currentHour / 48) * 100}%)`
                : 'var(--line)',
            }}
          />
        </div>
      </div>
    </div>
  );
}
