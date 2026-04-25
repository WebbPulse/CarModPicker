import type { PriceHistorySummary } from '../../types/Api';

interface PriceDeltaLineProps {
  summary: PriceHistorySummary | null | undefined;
}

const TREND_ARROW: Record<PriceHistorySummary['trend'], string> = {
  up: '↑',
  down: '↓',
  flat: '·',
};

function formatDollars(cents: number): string {
  return `$${Math.round(cents / 100).toLocaleString()}`;
}

function formatLocalDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function PriceDeltaLine({ summary }: PriceDeltaLineProps) {
  if (!summary) return null;
  if (summary.observation_count === 0) return null;

  const arrow = TREND_ARROW[summary.trend];

  if (summary.observation_count === 1) {
    const since =
      summary.last_observed_at !== null
        ? formatLocalDate(summary.last_observed_at)
        : 'recently';
    return (
      <span data-testid="price-delta-line" className="text-xs text-gray-400">
        <span data-testid="price-delta-arrow" aria-hidden="true">
          {arrow}
        </span>{' '}
        Tracked since {since}
      </span>
    );
  }

  // observation_count >= 2 — render min → max range without duration.
  // The summary lacks an earliest-observed timestamp, so the calendar-day
  // span between earliest and last_observed_at isn't computable here; per the
  // task plan this collapses to the "$<min> → $<max>" fallback.
  const minStr =
    summary.min_cents !== null ? formatDollars(summary.min_cents) : '—';
  const maxStr =
    summary.max_cents !== null ? formatDollars(summary.max_cents) : '—';

  return (
    <span data-testid="price-delta-line" className="text-xs text-gray-400">
      <span data-testid="price-delta-arrow" aria-hidden="true">
        {arrow}
      </span>{' '}
      {minStr} → {maxStr}
    </span>
  );
}
