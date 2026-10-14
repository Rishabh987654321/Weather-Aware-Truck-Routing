import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { HeatmapSlider } from './HeatmapSlider';
import { formatForecastTime } from '../utils/format';
import { useTripStore } from '../store/useTripStore';

describe('HeatmapSlider and Timeline Controls', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useTripStore.setState({
      heatmap: {
        start_time: '2026-10-14T11:00:00Z',
        hours: 49,
        points: [
          { lat: 33.0, lon: -97.0, intensity: Array.from({ length: 49 }, (_, i) => i * 0.02) },
          { lat: 34.0, lon: -98.0, intensity: Array.from({ length: 49 }, (_, i) => (i % 2 === 0 ? 0.5 : null)) },
        ],
      },
      heatmapStatus: 'success',
      heatHour: 0,
      showHeatmap: true,
      isPlaying: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('formats forecast hour and date correctly', () => {
    const formatted = formatForecastTime('2026-10-14T11:00:00Z', 12);
    expect(formatted.plusHours).toBe('+12h');
    expect(formatted.fullLabel).toContain('+12h');
  });

  it('slider change does NOT trigger any network request (spy on fetch)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<HeatmapSlider />);

    const slider = screen.getByLabelText(/forecast hour slider/i);
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveValue('0');

    // Simulate user dragging slider to hour 14
    fireEvent.change(slider, { target: { value: '14' } });

    expect(useTripStore.getState().heatHour).toBe(14);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('intensity selection for hour t picks index t from each point and filters nulls', () => {
    const { heatmap } = useTripStore.getState();
    const t = 10;

    // Simulate point extraction logic used in HeatLayer
    const extracted = [];
    for (const pt of heatmap.points) {
      const val = pt.intensity[t];
      if (val != null && val > 0) {
        extracted.push({ lat: pt.lat, lon: pt.lon, intensity: val });
      }
    }

    // Point 1 has 10 * 0.02 = 0.20
    expect(extracted[0].intensity).toBeCloseTo(0.20);
    // Point 2 has 0.5 (since 10 % 2 === 0)
    expect(extracted[1].intensity).toBeCloseTo(0.5);

    // For an odd hour where Point 2 is null:
    const tOdd = 11;
    const extractedOdd = [];
    for (const pt of heatmap.points) {
      const val = pt.intensity[tOdd];
      if (val != null && val > 0) {
        extractedOdd.push({ lat: pt.lat, lon: pt.lon, intensity: val });
      }
    }
    // Only Point 1 included (Point 2 is null)
    expect(extractedOdd.length).toBe(1);
    expect(extractedOdd[0].intensity).toBeCloseTo(0.22);
  });

  it('toggles heatmap layer visibility and play state', () => {
    render(<HeatmapSlider />);

    const toggleBtn = screen.getByTitle(/hide forecast heatmap/i);
    expect(toggleBtn).toBeInTheDocument();

    // Toggle off
    fireEvent.click(toggleBtn);
    expect(useTripStore.getState().showHeatmap).toBe(false);

    // Toggle back on
    fireEvent.click(toggleBtn);
    expect(useTripStore.getState().showHeatmap).toBe(true);

    // Play/Pause button
    const playBtn = screen.getByTitle(/play timeline animation/i);
    fireEvent.click(playBtn);
    expect(useTripStore.getState().isPlaying).toBe(true);

    fireEvent.click(playBtn);
    expect(useTripStore.getState().isPlaying).toBe(false);
  });

  it('disables play button and slider, stops playback, and dims legend when heatmap is off', () => {
    // Start with playback active
    useTripStore.setState({ isPlaying: true, showHeatmap: true });
    render(<HeatmapSlider />);

    const toggleBtn = screen.getByTitle(/hide forecast heatmap/i);
    const playBtn = screen.getByRole('button', { name: /pause forecast timeline/i });
    const slider = screen.getByLabelText(/forecast hour slider/i);
    const legend = screen.getByText('Low').parentElement;

    expect(playBtn).toBeEnabled();
    expect(slider).toBeEnabled();
    expect(legend).toHaveStyle({ opacity: '1' });

    // Toggle off
    fireEvent.click(toggleBtn);

    // Playback must stop immediately
    expect(useTripStore.getState().isPlaying).toBe(false);
    expect(useTripStore.getState().showHeatmap).toBe(false);

    // Controls must be disabled and visibly dimmed
    expect(playBtn).toBeDisabled();
    expect(playBtn).toHaveStyle({ opacity: '0.4' });
    expect(slider).toBeDisabled();
    expect(slider).toHaveStyle({ opacity: '0.4' });
    expect(legend).toHaveStyle({ opacity: '0.35' });
  });

  it('shows calm corridor note when current hour max intensity < 0.25', () => {
    // Setup calm data for hour 0 (point 0 has 0, point 1 has 0)
    useTripStore.setState({
      heatHour: 0,
      heatmap: {
        start_time: '2026-10-14T11:00:00Z',
        hours: 49,
        points: [
          { lat: 33.0, lon: -97.0, intensity: Array(49).fill(0.12) },
          { lat: 34.0, lon: -98.0, intensity: Array(49).fill(0.18) },
        ],
      },
      showHeatmap: true,
    });

    render(<HeatmapSlider />);

    expect(
      screen.getByText(/forecast is calm along this corridor at this hour/i)
    ).toBeInTheDocument();
  });

  it('hides calm corridor note when max intensity is >= 0.25', () => {
    useTripStore.setState({
      heatHour: 0,
      heatmap: {
        start_time: '2026-10-14T11:00:00Z',
        hours: 49,
        points: [
          { lat: 33.0, lon: -97.0, intensity: Array(49).fill(0.12) },
          { lat: 34.0, lon: -98.0, intensity: Array(49).fill(0.65) },
        ],
      },
      showHeatmap: true,
    });

    render(<HeatmapSlider />);

    expect(
      screen.queryByText(/forecast is calm along this corridor at this hour/i)
    ).not.toBeInTheDocument();
  });
});
