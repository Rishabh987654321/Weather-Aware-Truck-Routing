import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

// Helper for default departure (now + 1h formatted for datetime-local)
function getDefaultDepartureLocal() {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  const year = d.getFullYear();
  const month = pad(d.getMonth() + 1);
  const day = pad(d.getDate());
  const hours = pad(d.getHours());
  const mins = pad(d.getMinutes());
  return `${year}-${month}-${day}T${hours}:${mins}`;
}

export const useTripStore = create(
  subscribeWithSelector((set) => ({
    form: {
      origin: { lat: 32.7767, lon: -96.7970, label: 'Dallas, TX' },
      destination: { lat: 39.7392, lon: -104.9903, label: 'Denver, CO' },
      departure_time: getDefaultDepartureLocal(),
      load_lbs: 42000,
    },
    status: 'idle', // 'idle' | 'loading' | 'success' | 'error'
    analysis: null,
    error: null,
    fieldErrors: {},
    selectedRouteId: null,
    activeCheckpointIndex: null,
    heatmap: null,
    heatmapStatus: 'idle', // 'idle' | 'loading' | 'success' | 'error'
    heatHour: 0,
    showHeatmap: true,
    isPlaying: false,

    setForm: (form) => set({ form }),
    setStatus: (status) => set({ status }),
    setAnalysis: (analysis) =>
      set({
        analysis,
        selectedRouteId: analysis?.recommended_route_id || analysis?.routes?.[0]?.id || null,
        status: 'success',
        error: null,
        fieldErrors: {},
      }),
    setError: (error, fieldErrors = {}) =>
      set({
        error,
        fieldErrors,
        status: 'error',
      }),
    setSelectedRouteId: (selectedRouteId) => set({ selectedRouteId }),
    setActiveCheckpointIndex: (activeCheckpointIndex) => set({ activeCheckpointIndex }),
    setHeatmap: (heatmap) => {
      if (heatmap && heatmap.points) {
        const hoursCount = heatmap.hours || 49;
        const maxArr = new Float32Array(hoursCount);
        const pts = heatmap.points;
        const numPts = pts.length;
        for (let h = 0; h < hoursCount; h++) {
          let maxVal = 0;
          for (let i = 0; i < numPts; i++) {
            const val = pts[i].intensity?.[h] || 0;
            if (val > maxVal) maxVal = val;
          }
          maxArr[h] = maxVal;
        }
        heatmap.maxByHour = maxArr;
      }
      set({ heatmap, heatmapStatus: 'success' });
    },
    setHeatmapStatus: (heatmapStatus) => set({ heatmapStatus }),
    setHeatHour: (heatHour) =>
      set((state) => ({
        heatHour: typeof heatHour === 'function' ? heatHour(state.heatHour) : heatHour,
      })),
    setShowHeatmap: (showHeatmap) => set({ showHeatmap }),
    setIsPlaying: (isPlaying) => set({ isPlaying }),
    reset: () =>
      set({
        status: 'idle',
        analysis: null,
        error: null,
        fieldErrors: {},
        selectedRouteId: null,
        activeCheckpointIndex: null,
        heatmap: null,
        heatmapStatus: 'idle',
        heatHour: 0,
        isPlaying: false,
      }),
  }))
);
