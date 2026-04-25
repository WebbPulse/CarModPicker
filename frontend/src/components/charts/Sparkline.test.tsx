import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Sparkline from './Sparkline';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';

function obs(
  id: string,
  cents: number,
  observed_at: string,
): PartPriceHistoryReadWithRetailer {
  return {
    id,
    part_listing_id: `pl-${id}`,
    price_cents: cents,
    observed_at,
    retailer_id: 'r1',
    retailer_name: 'AmazingMart',
  };
}

describe('Sparkline', () => {
  it('renders nothing when history is empty', () => {
    const { container } = render(<Sparkline history={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a single filled dot when history has exactly one observation', () => {
    const { container } = render(
      <Sparkline history={[obs('1', 4999, '2026-04-01T00:00:00Z')]} />,
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    const dot = container.querySelector('[data-testid="sparkline-dot"]');
    expect(dot).not.toBeNull();
    // No polyline path when there's only one point
    expect(
      container.querySelector('[data-testid="sparkline-polyline"]'),
    ).toBeNull();
  });

  it('renders a polyline when history has multiple observations', () => {
    const history = [
      obs('1', 5000, '2026-03-01T00:00:00Z'),
      obs('2', 4500, '2026-03-15T00:00:00Z'),
      obs('3', 4800, '2026-04-01T00:00:00Z'),
    ];
    const { container } = render(<Sparkline history={history} />);
    const polyline = container.querySelector(
      '[data-testid="sparkline-polyline"]',
    );
    expect(polyline).not.toBeNull();
    const points = polyline?.getAttribute('points') ?? '';
    // Three points → three coordinate pairs
    expect(points.split(' ').filter(Boolean)).toHaveLength(3);
    expect(polyline?.getAttribute('preserveAspectRatio')).toBeNull();
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('preserveAspectRatio')).toBe('none');
    expect(polyline?.getAttribute('stroke')).toBe('hsl(var(--primary))');
    expect(polyline?.getAttribute('stroke-width')).toBe('1.5');
  });

  it('sorts observations by observed_at ascending before plotting', () => {
    // Provide unsorted input — first point in `points` should reflect the
    // earliest observation (lowest cents here is at the earliest date).
    const history = [
      obs('late', 6000, '2026-04-10T00:00:00Z'),
      obs('early', 1000, '2026-01-01T00:00:00Z'),
      obs('mid', 3000, '2026-02-15T00:00:00Z'),
    ];
    const { container } = render(<Sparkline history={history} />);
    const polyline = container.querySelector(
      '[data-testid="sparkline-polyline"]',
    );
    const points = (polyline?.getAttribute('points') ?? '')
      .split(' ')
      .filter(Boolean);
    // First point in plot order is x=0 (earliest), last is x=width.
    // y is normalized so the minimum price (1000) maps to the largest y.
    expect(points[0]?.startsWith('0,')).toBe(true);
  });

  it('uses provided ariaLabel for accessibility', () => {
    render(
      <Sparkline
        history={[
          obs('1', 1000, '2026-01-01T00:00:00Z'),
          obs('2', 2000, '2026-02-01T00:00:00Z'),
        ]}
        ariaLabel="Brake pad price trend"
      />,
    );
    expect(
      screen.getByRole('img', { name: 'Brake pad price trend' }),
    ).toBeInTheDocument();
  });

  it('handles flat price series without dividing by zero', () => {
    const history = [
      obs('1', 5000, '2026-01-01T00:00:00Z'),
      obs('2', 5000, '2026-02-01T00:00:00Z'),
      obs('3', 5000, '2026-03-01T00:00:00Z'),
    ];
    const { container } = render(<Sparkline history={history} />);
    const polyline = container.querySelector(
      '[data-testid="sparkline-polyline"]',
    );
    const points = (polyline?.getAttribute('points') ?? '')
      .split(' ')
      .filter(Boolean);
    // All y values should equal height/2 (default 24/2 = 12) when range is 0
    points.forEach((p) => {
      const [, y] = p.split(',');
      expect(Number(y)).toBe(12);
    });
  });
});
