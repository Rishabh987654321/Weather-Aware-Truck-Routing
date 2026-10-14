import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import { useTripStore } from '../store/useTripStore';
import { formatDurationDelta } from '../utils/format';
import dallasDenverMock from '../mocks/analyze-dallas-denver.json';
import { createMockHeatmap } from '../mocks/heatmapMock';

describe('Phase 6 Regression & Bug Fix Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('Delta pills logic across 3 routes', () => {
    const r1 = { id: 'r1', duration_s: 50000 };
    const r2 = { id: 'r2', duration_s: 54000 };
    const r3 = { id: 'r3', duration_s: 59840 }; // 9840s = 164 mins difference from r1

    it('calculates alternate route delta relative to selected route (when r1 selected)', () => {
      const selected = r1;
      expect(formatDurationDelta(r2.duration_s, selected.duration_s)).toBe('67 min slower');
      expect(formatDurationDelta(r3.duration_s, selected.duration_s)).toBe('164 min slower');
    });

    it('calculates alternate route delta relative to selected route (when r3 selected)', () => {
      const selected = r3;
      // When r3 is selected, r1 is 164 min faster, matching the panel!
      expect(formatDurationDelta(r1.duration_s, selected.duration_s)).toBe('164 min faster');
      expect(formatDurationDelta(r2.duration_s, selected.duration_s)).toBe('97 min faster');
    });

    it('calculates alternate route delta relative to selected route (when r2 selected)', () => {
      const selected = r2;
      expect(formatDurationDelta(r1.duration_s, selected.duration_s)).toBe('67 min faster');
      expect(formatDurationDelta(r3.duration_s, selected.duration_s)).toBe('97 min slower');
    });
  });

  describe('Marker and Layer stability across heatHour ticks', () => {
    it('advancing heatHour 10 times preserves marker DOM node identity and does not recreate them', async () => {
      // Set initial store state with mock analysis
      useTripStore.setState({
        status: 'success',
        analysis: dallasDenverMock,
        heatmap: createMockHeatmap(),
        heatmapStatus: 'success',
        selectedRouteId: dallasDenverMock.routes[0].id,
        heatHour: 0,
        showHeatmap: true,
        isPlaying: false,
      });

      const { container } = render(<App />);

      // Query checkpoint marker dots on the map
      const initialMarkers = Array.from(container.querySelectorAll('.cp__dot'));
      expect(initialMarkers.length).toBeGreaterThan(0);

      // Advance heatHour 10 times (simulating 10 ticks of playback / dragging)
      for (let h = 1; h <= 10; h++) {
        act(() => {
          useTripStore.getState().setHeatHour(h);
        });
      }

      // Checkpoint marker dots must have the EXACT SAME DOM identities
      const currentMarkers = Array.from(container.querySelectorAll('.cp__dot'));
      expect(currentMarkers.length).toBe(initialMarkers.length);

      for (let i = 0; i < initialMarkers.length; i++) {
        expect(currentMarkers[i]).toBe(initialMarkers[i]);
      }

      // Heatmap slider value must update to 10
      const slider = screen.getByLabelText(/forecast hour slider/i);
      expect(slider).toHaveValue('10');
    });
  });
});
