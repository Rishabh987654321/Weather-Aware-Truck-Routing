import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import RouteRows from './components/RouteRows';
import SearchForm from './components/SearchForm';

describe('RouteRows', () => {
  const mockRoutes = [
    {
      id: 'r1',
      distance_mi: 795,
      duration_s: 54000,
      avg_risk: 1.4,
      blocked: false,
      miles_by_level: { low: 700, moderate: 95 },
      checkpoints: [
        { mile: 0, level: 'low', eta_utc: '2026-10-14T08:00:00Z' },
        { mile: 795, level: 'low', eta_utc: '2026-10-14T23:00:00Z' },
      ],
    },
    {
      id: 'r2',
      distance_mi: 881,
      duration_s: 57600,
      avg_risk: null, // Test avg_risk null renders 'n/a'
      blocked: true, // Test blocked tag
      miles_by_level: { low: 600, no_travel: 100, unknown: 181 },
      checkpoints: [
        { mile: 0, level: 'low', eta_utc: '2026-10-14T08:00:00Z' },
        { mile: 881, level: 'no_travel', eta_utc: '2026-10-15T00:00:00Z' },
      ],
    },
  ];

  it('renders Recommended badge on the correct route and translates IDs', () => {
    render(
      <RouteRows
        routes={mockRoutes}
        recommendedRouteId="r1"
        selectedRouteId="r1"
        reason="Tied on weather risk; faster by 60 min than r2."
      />
    );

    // Recommended badge present
    expect(screen.getByText('Recommended')).toBeInTheDocument();
    // Route names mapped to Route 1 and Route 2
    expect(screen.getByText('Route 1')).toBeInTheDocument();
    expect(screen.getByText('Route 2')).toBeInTheDocument();
    // Reason text translates r2 to Route 2
    expect(screen.getByText(/faster by 60 min than Route 2/i)).toBeInTheDocument();
  });

  it('renders "n/a" when avg_risk is null and renders Blocked tag', () => {
    render(
      <RouteRows
        routes={mockRoutes}
        recommendedRouteId="r1"
        selectedRouteId="r1"
      />
    );

    // avg_risk null on r2 renders 'n/a'
    expect(screen.getByText(/risk n\/a/i)).toBeInTheDocument();
    // Blocked tag on r2
    expect(screen.getByText('Blocked')).toBeInTheDocument();
  });
});

describe('SearchForm validation', () => {
  const validForm = {
    origin: { lat: 32.7767, lon: -96.7970, label: 'Dallas, TX' },
    destination: { lat: 39.7392, lon: -104.9903, label: 'Denver, CO' },
    departure_time: '2026-10-14T08:00',
    load_lbs: 42000,
  };

  it('disables submit button when load is 0 or less', () => {
    const invalidForm = { ...validForm, load_lbs: 0 };
    render(
      <SearchForm
        form={invalidForm}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );
    const button = screen.getByRole('button', { name: /find safest route/i });
    expect(button).toBeDisabled();
  });

  it('disables submit button when origin equals destination', () => {
    const samePlaceForm = {
      ...validForm,
      destination: { lat: 32.7767, lon: -96.7970, label: 'Dallas, TX' },
    };
    render(
      <SearchForm
        form={samePlaceForm}
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />
    );
    const button = screen.getByRole('button', { name: /find safest route/i });
    expect(button).toBeDisabled();
  });

  it('disables submit button when origin or destination is missing', () => {
    const missingOrigin = { ...validForm, origin: null };
    const { rerender } = render(
      <SearchForm form={missingOrigin} onChange={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByRole('button', { name: /find safest route/i })).toBeDisabled();

    const missingDest = { ...validForm, destination: null };
    rerender(<SearchForm form={missingDest} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByRole('button', { name: /find safest route/i })).toBeDisabled();
  });

  it('enables submit button and calls onSubmit when form is valid', () => {
    const handleSubmit = vi.fn();
    render(
      <SearchForm
        form={validForm}
        onChange={vi.fn()}
        onSubmit={handleSubmit}
      />
    );
    const button = screen.getByRole('button', { name: /find safest route/i });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(handleSubmit).toHaveBeenCalledTimes(1);
  });
});

describe('MapView checkpoint markers', () => {
  it('excludes checkpoint markers at mile 0 and at the final mile', async () => {
    const { filterVisibleCheckpoints } = await import('./utils/format');
    const checkpoints = [
      { mile: 0, lat: 32.7, lon: -96.8, level: 'low' },
      { mile: 150, lat: 34.1, lon: -98.2, level: 'moderate' },
      { mile: 300, lat: 36.5, lon: -100.1, level: 'high' },
      { mile: 450, lat: 38.2, lon: -102.5, level: 'severe' },
      { mile: 600, lat: 39.7, lon: -104.9, level: 'low' },
    ];
    const visible = filterVisibleCheckpoints(checkpoints, 600);

    // Only intermediate checkpoints (mile 150, 300, 450) must be included
    expect(visible).toHaveLength(3);
    expect(visible[0].mile).toBe(150);
    expect(visible[1].mile).toBe(300);
    expect(visible[2].mile).toBe(450);

    // Verify mile 0 and mile 600 are omitted
    expect(visible.some((cp) => cp.mile === 0)).toBe(false);
    expect(visible.some((cp) => cp.mile === 600)).toBe(false);
  });
});
