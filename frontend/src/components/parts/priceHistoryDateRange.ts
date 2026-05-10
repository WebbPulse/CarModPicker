/** Calendar-anchored date-range picker options used by the part-detail
 *  price history chart. Kept separate from the chart component so that
 *  ViewPart can derive the same calendar cutoff for sparklines (and any
 *  future consumer) without dragging in the whole SVG component. */
export type DateRangeOption =
  | 'this_year'
  | 'this_month'
  | 'this_week'
  | 'all_time';

/** Lower bound (in epoch ms) for filtering observations to the selected
 *  range. Returns null for `all_time` (no lower bound). */
export function getDateRangeStartMs(range: DateRangeOption): number | null {
  const today = new Date();
  switch (range) {
    case 'this_year':
      return new Date(today.getFullYear(), 0, 1).getTime();
    case 'this_month':
      return new Date(today.getFullYear(), today.getMonth(), 1).getTime();
    case 'this_week': {
      const dayOfWeek = today.getDay();
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - dayOfWeek);
      weekStart.setHours(0, 0, 0, 0);
      return weekStart.getTime();
    }
    case 'all_time':
      return null;
  }
}
