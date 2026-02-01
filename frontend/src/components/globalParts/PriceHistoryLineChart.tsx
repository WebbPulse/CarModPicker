import { useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { PartPriceHistoryReadWithRetailer } from '../../types/Api';

/** Distinct colors for retailer lines - visible on dark backgrounds */
const RETAILER_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#84cc16', // lime
  '#f97316', // orange
  '#6366f1', // indigo
];

const DEFAULT_PADDING = { top: 20, right: 20, bottom: 50, left: 60 };

/** Minimum x-axis range when there are few data points (7 days) so scale/labels look sensible */
const MIN_X_RANGE_MS = 7 * 24 * 60 * 60 * 1000;

/** Minimum y-axis step in cents ($10) so ticks are at least $10 apart */
const MIN_Y_STEP_CENTS = 1000;

interface PriceHistoryLineChartProps {
  data: PartPriceHistoryReadWithRetailer[];
  width?: number;
  height?: number;
  padding?: { top: number; right: number; bottom: number; left: number };
}

export default function PriceHistoryLineChart({
  data,
  width = 700,
  height = 350,
  padding = DEFAULT_PADDING,
}: PriceHistoryLineChartProps) {
  const chartData = useMemo(() => {
    if (data.length === 0) return null;

    // Aggregate to one point per (retailer, calendar day) - keep latest observation per day
    // Use local timezone so dates align with user's local calendar
    const dayKey = (iso: string) => {
      const d = new Date(iso);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };
    const dayStartMs = (iso: string) => {
      const d = new Date(iso);
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    const byRetailerDay = new Map<string, PartPriceHistoryReadWithRetailer>();
    for (const d of data) {
      const key = `${d.retailer_name}\0${dayKey(d.observed_at)}`;
      const existing = byRetailerDay.get(key);
      if (
        !existing ||
        new Date(d.observed_at).getTime() >
          new Date(existing.observed_at).getTime()
      ) {
        byRetailerDay.set(key, d);
      }
    }
    const aggregated = [...byRetailerDay.values()];

    const today = new Date();

    const dates = aggregated.map((d) => dayStartMs(d.observed_at));
    const oldestData = Math.min(...dates);
    const newestData = Math.max(...dates);

    const MS_PER_DAY = 24 * 60 * 60 * 1000;

    // X-axis: snap to local calendar day boundaries so data points align exactly on days
    const todayStart = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate()
    ).getTime();
    let xMin = Math.min(oldestData, todayStart);
    let xMax = Math.max(newestData + MS_PER_DAY, todayStart + MS_PER_DAY);
    let xRange = xMax - xMin;
    if (xRange < MIN_X_RANGE_MS) {
      const centerDate = new Date((xMin + xMax) / 2);
      const centerDayStart = new Date(
        centerDate.getFullYear(),
        centerDate.getMonth(),
        centerDate.getDate()
      ).getTime();
      xMin = centerDayStart - MIN_X_RANGE_MS / 2;
      xMax = xMin + MIN_X_RANGE_MS;
      xRange = MIN_X_RANGE_MS;
    }

    const prices = aggregated.map((d) => d.price_cents);
    const priceMin = Math.min(...prices);
    const priceMax = Math.max(...prices);
    const pricePadding = Math.max((priceMax - priceMin) * 0.1, 100);
    const rawYMin = Math.max(0, priceMin - pricePadding);
    const rawYMax = priceMax + pricePadding;

    // Y-axis: step of at least $10 (MIN_Y_STEP_CENTS). Snap bounds to step and cap tick count.
    let yStep = MIN_Y_STEP_CENTS;
    let yMin = Math.floor(rawYMin / yStep) * yStep;
    let yMax = Math.ceil(rawYMax / yStep) * yStep;
    let tickCount = (yMax - yMin) / yStep;
    const maxTicks = 12;
    while (tickCount > maxTicks && yStep < 100000) {
      yStep *= 2;
      yMin = Math.floor(rawYMin / yStep) * yStep;
      yMax = Math.ceil(rawYMax / yStep) * yStep;
      tickCount = (yMax - yMin) / yStep;
    }
    const yRange = yMax - yMin || 1;

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const xScale = (t: number) =>
      padding.left + ((t - xMin) / xRange) * chartWidth;
    const yScale = (c: number) =>
      padding.top + chartHeight - ((c - yMin) / yRange) * chartHeight;

    const retailers = [...new Set(aggregated.map((d) => d.retailer_name))];
    const retailerColors = Object.fromEntries(
      retailers.map((name, i) => [
        name,
        RETAILER_COLORS[i % RETAILER_COLORS.length],
      ])
    );

    const lines = retailers.map((retailerName) => {
      const points = aggregated
        .filter((d) => d.retailer_name === retailerName)
        .map((d) => ({
          x: dayStartMs(d.observed_at),
          y: d.price_cents,
          observedAt: d.observed_at,
        }))
        .sort((a, b) => a.x - b.x);

      const pathD = points
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(p.x)} ${yScale(p.y)}`)
        .join(' ');

      return {
        retailerName,
        color: retailerColors[retailerName] ?? RETAILER_COLORS[0],
        pathD,
        points,
      };
    });

    const formatXLabel = (d: Date) =>
      d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year:
          d.getFullYear() !== new Date().getFullYear() ? '2-digit' : undefined,
      });

    const formatYLabel = (v: number) => `$${(v / 100).toFixed(0)}`;

    // X-axis ticks at local calendar day boundaries so labels align with data points
    const xTickValuesRaw: Date[] = [];
    const startDate = new Date(xMin);
    const maxXTicks = 8;
    const dayCount = Math.ceil(xRange / MS_PER_DAY);
    const step = Math.max(1, Math.ceil(dayCount / maxXTicks));
    let tickDate = new Date(
      startDate.getFullYear(),
      startDate.getMonth(),
      startDate.getDate()
    );
    while (tickDate.getTime() < xMax) {
      xTickValuesRaw.push(new Date(tickDate));
      tickDate.setDate(tickDate.getDate() + step);
    }

    // Only include ticks within the visible range so labels don't overflow or overlap
    const visibleTicks = xTickValuesRaw.filter((d) => d.getTime() >= xMin);

    // Deduplicate: keep only one label per unique date
    const xTickValues = visibleTicks.filter(
      (d, i) =>
        i === 0 || formatXLabel(d) !== formatXLabel(visibleTicks[i - 1]!)
    );

    // Y ticks at step intervals ($10 minimum), top to bottom
    const yTickValuesRaw: number[] = [];
    for (let v = yMax; v >= yMin; v -= yStep) {
      yTickValuesRaw.push(v);
    }
    const yTickValues = yTickValuesRaw;

    return {
      xMin,
      xMax,
      yMin,
      yMax,
      xScale,
      yScale,
      lines,
      retailerColors,
      xTickValues,
      yTickValues,
      xTickValuesGrid: visibleTicks,
      yTickValuesGrid: yTickValuesRaw,
      formatXLabel,
      formatYLabel,
      chartWidth,
      chartHeight,
    };
  }, [data, width, height, padding]);

  const [hoveredPoint, setHoveredPoint] = useState<{
    cx: number;
    cy: number;
    entries: Array<{
      retailerName: string;
      observedAt: string;
      priceCents: number;
    }>;
  } | null>(null);

  /** Pixel distance within which points are considered co-located (multiple retailers at same spot) */
  const CO_LOCATED_THRESHOLD = 16;

  const svgRef = useRef<SVGSVGElement>(null);

  const formatTooltipDate = (iso: string) =>
    new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });

  if (!chartData || data.length === 0) return null;

  const {
    lines,
    xTickValues,
    yTickValues,
    xTickValuesGrid,
    yTickValuesGrid,
    formatXLabel,
    formatYLabel,
  } = chartData;

  return (
    <div className="relative w-full overflow-x-auto" dir="ltr">
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="min-w-[400px]"
        role="img"
        aria-label="Price history by retailer"
        style={{ direction: 'ltr' }}
      >
        {/* Grid lines (use full tick set for even spacing) */}
        {yTickValuesGrid.slice(1, -1).map((v) => (
          <line
            key={`grid-y-${v}`}
            x1={padding.left}
            y1={chartData.yScale(v)}
            x2={width - padding.right}
            y2={chartData.yScale(v)}
            stroke="currentColor"
            strokeOpacity={0.15}
            strokeDasharray="4 4"
          />
        ))}
        {xTickValuesGrid.map((d) => (
          <line
            key={`grid-x-${d.getTime()}`}
            x1={chartData.xScale(d.getTime())}
            y1={padding.top}
            x2={chartData.xScale(d.getTime())}
            y2={height - padding.bottom}
            stroke="currentColor"
            strokeOpacity={0.15}
            strokeDasharray="4 4"
          />
        ))}

        {/* Y-axis labels */}
        {yTickValues.map((v) => (
          <text
            key={`y-${v}`}
            x={padding.left - 8}
            y={chartData.yScale(v)}
            textAnchor="end"
            dominantBaseline="middle"
            className="fill-gray-400 text-xs"
          >
            {formatYLabel(v)}
          </text>
        ))}

        {/* X-axis labels - center all under their grid lines for consistent alignment */}
        {xTickValues.map((d) => (
          <text
            key={`x-${d.getTime()}`}
            x={chartData.xScale(d.getTime())}
            y={height - padding.bottom + 20}
            textAnchor="middle"
            className="fill-gray-400 text-xs"
          >
            {formatXLabel(d)}
          </text>
        ))}

        {/* Axis lines */}
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={height - padding.bottom}
          stroke="currentColor"
          strokeOpacity={0.3}
          strokeWidth={1}
        />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          stroke="currentColor"
          strokeOpacity={0.3}
          strokeWidth={1}
        />

        {/* Data lines - use full color always; dim non-hovered when hovering */}
        {lines.map(({ retailerName, color, pathD, points }) => {
          const isHoveredLine = hoveredPoint?.entries.some(
            (e) => e.retailerName === retailerName
          );
          const strokeColor = color;
          const strokeOpacity = hoveredPoint ? (isHoveredLine ? 1 : 0.25) : 1;
          const lastPoint = points[points.length - 1];
          return (
            <g key={retailerName}>
              <path
                d={pathD}
                fill="none"
                stroke={strokeColor}
                strokeOpacity={strokeOpacity}
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{
                  transition: 'stroke 0.15s ease, stroke-opacity 0.15s ease',
                }}
              />
              {/* Invisible wide stroke for line hover - render before point hit areas so points take precedence */}
              <path
                d={pathD}
                fill="none"
                stroke="transparent"
                strokeWidth={16}
                strokeLinecap="round"
                strokeLinejoin="round"
                onMouseEnter={() =>
                  lastPoint &&
                  setHoveredPoint({
                    cx: chartData.xScale(lastPoint.x),
                    cy: chartData.yScale(lastPoint.y),
                    entries: [
                      {
                        retailerName,
                        observedAt: lastPoint.observedAt,
                        priceCents: lastPoint.y,
                      },
                    ],
                  })
                }
                onMouseLeave={() => setHoveredPoint(null)}
                className="cursor-pointer"
              />
            </g>
          );
        })}

        {/* Data points - invisible larger hit area for easier hovering */}
        {lines.map(({ retailerName, color, points }) =>
          points.map((p) => {
            const cx = chartData.xScale(p.x);
            const cy = chartData.yScale(p.y);
            const isHoveredLine = hoveredPoint?.entries.some(
              (e) => e.retailerName === retailerName
            );
            const pointColor =
              hoveredPoint && !isHoveredLine ? '#6b7280' : color;
            const pointOpacity = hoveredPoint && !isHoveredLine ? 0.4 : 1;
            return (
              <g key={`${retailerName}-${p.x}`}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={12}
                  fill="transparent"
                  onMouseEnter={() => {
                    const entries: Array<{
                      retailerName: string;
                      observedAt: string;
                      priceCents: number;
                    }> = [];
                    for (const line of lines) {
                      for (const pt of line.points) {
                        const pcx = chartData.xScale(pt.x);
                        const pcy = chartData.yScale(pt.y);
                        if (
                          Math.hypot(cx - pcx, cy - pcy) <= CO_LOCATED_THRESHOLD
                        ) {
                          entries.push({
                            retailerName: line.retailerName,
                            observedAt: pt.observedAt,
                            priceCents: pt.y,
                          });
                        }
                      }
                    }
                    setHoveredPoint({ cx, cy, entries });
                  }}
                  onMouseLeave={() => setHoveredPoint(null)}
                  className="cursor-pointer"
                />
                <circle
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill={pointColor}
                  fillOpacity={pointOpacity}
                  stroke="rgb(15 23 42)"
                  strokeWidth={1}
                  pointerEvents="none"
                  style={{
                    transition: 'fill 0.15s ease, fill-opacity 0.15s ease',
                  }}
                />
              </g>
            );
          })
        )}
      </svg>

      {/* Hover tooltip - rendered via portal so it can overflow outside the chart container */}
      {hoveredPoint &&
        svgRef.current &&
        (() => {
          const rect = svgRef.current.getBoundingClientRect();
          return createPortal(
            <div
              className="pointer-events-none fixed z-[9999] rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 shadow-lg"
              style={{
                left: rect.left + hoveredPoint.cx,
                top: rect.top + hoveredPoint.cy,
                transform: 'translate(-50%, calc(-100% - 10px))',
              }}
            >
              {hoveredPoint.entries.map((entry, i) => (
                <div
                  key={`${entry.retailerName}-${entry.observedAt}-${i}`}
                  className={i > 0 ? 'mt-2 border-t border-gray-600 pt-2' : ''}
                >
                  <div className="font-medium">{entry.retailerName}</div>
                  <div className="mt-0.5 text-gray-300">
                    {formatTooltipDate(entry.observedAt)}
                  </div>
                  <div className="mt-0.5 font-medium">
                    ${(entry.priceCents / 100).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>,
            document.body
          );
        })()}

      {/* Legend - dim non-hovered when a point is hovered */}
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {lines.map(({ retailerName, color }) => {
          const isHoveredLine = hoveredPoint?.entries.some(
            (e) => e.retailerName === retailerName
          );
          const dimmed = hoveredPoint && !isHoveredLine;
          return (
            <div
              key={retailerName}
              className={`flex items-center gap-2 transition-opacity duration-150 ${
                dimmed ? 'opacity-40' : ''
              }`}
            >
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{
                  backgroundColor: dimmed ? '#6b7280' : color,
                }}
                aria-hidden
              />
              <span className="text-sm text-gray-300">{retailerName}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
