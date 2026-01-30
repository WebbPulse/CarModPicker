import { useMemo, useState } from 'react';
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

    const today = new Date();
    today.setHours(23, 59, 59, 999);
    const todayTime = today.getTime();

    const dates = data.map((d) => new Date(d.observed_at).getTime());
    const oldestData = Math.min(...dates);
    const newestData = Math.max(...dates);

    // X-axis: oldest (left) to newest (right). Use a minimum range when few points so scale/labels make sense.
    let xMin = Math.min(oldestData, todayTime);
    let xMax = Math.max(newestData, todayTime);
    let xRange = xMax - xMin;
    if (xRange < MIN_X_RANGE_MS) {
      const center = (xMin + xMax) / 2;
      xMin = center - MIN_X_RANGE_MS / 2;
      xMax = center + MIN_X_RANGE_MS / 2;
      xRange = MIN_X_RANGE_MS;
    }

    const prices = data.map((d) => d.price_cents);
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

    const retailers = [...new Set(data.map((d) => d.retailer_name))];
    const retailerColors = Object.fromEntries(
      retailers.map((name, i) => [
        name,
        RETAILER_COLORS[i % RETAILER_COLORS.length],
      ])
    );

    const lines = retailers.map((retailerName) => {
      const points = data
        .filter((d) => d.retailer_name === retailerName)
        .map((d) => ({
          x: new Date(d.observed_at).getTime(),
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

    const xTicks = 5;
    const xTickValuesRaw = Array.from({ length: xTicks + 1 }, (_, i) => {
      const t = xMin + (xRange * i) / xTicks;
      return new Date(t);
    }).sort((a, b) => a.getTime() - b.getTime());

    // Deduplicate: keep only one label per unique date
    const xTickValues = xTickValuesRaw.filter(
      (d, i) =>
        i === 0 || formatXLabel(d) !== formatXLabel(xTickValuesRaw[i - 1]!)
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
      xTickValuesGrid: xTickValuesRaw,
      yTickValuesGrid: yTickValuesRaw,
      formatXLabel,
      formatYLabel,
      chartWidth,
      chartHeight,
    };
  }, [data, width, height, padding]);

  const [hoveredPoint, setHoveredPoint] = useState<{
    retailerName: string;
    observedAt: string;
    priceCents: number;
    cx: number;
    cy: number;
  } | null>(null);

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
        {xTickValuesGrid.slice(1, -1).map((d) => (
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

        {/* X-axis labels */}
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

        {/* Data lines - dim non-hovered when hovering over a point */}
        {lines.map(({ retailerName, color, pathD }) => {
          const isHoveredLine = hoveredPoint?.retailerName === retailerName;
          const strokeColor = isHoveredLine ? color : '#6b7280';
          const strokeOpacity = hoveredPoint ? (isHoveredLine ? 1 : 0.25) : 1;
          return (
            <path
              key={retailerName}
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
          );
        })}

        {/* Data points - invisible larger hit area for easier hovering */}
        {lines.map(({ retailerName, color, points }) =>
          points.map((p) => {
            const cx = chartData.xScale(p.x);
            const cy = chartData.yScale(p.y);
            const isHoveredLine = hoveredPoint?.retailerName === retailerName;
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
                  onMouseEnter={() =>
                    setHoveredPoint({
                      retailerName,
                      observedAt: p.observedAt,
                      priceCents: p.y,
                      cx,
                      cy,
                    })
                  }
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

      {/* Hover tooltip */}
      {hoveredPoint && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-100 shadow-lg"
          style={{
            left: hoveredPoint.cx,
            top: hoveredPoint.cy,
            transform: 'translate(-50%, calc(-100% - 10px))',
          }}
        >
          <div className="font-medium">{hoveredPoint.retailerName}</div>
          <div className="mt-0.5 text-gray-300">
            {formatTooltipDate(hoveredPoint.observedAt)}
          </div>
          <div className="mt-0.5 font-medium">
            ${(hoveredPoint.priceCents / 100).toFixed(2)}
          </div>
        </div>
      )}

      {/* Legend - dim non-hovered when a point is hovered */}
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
        {lines.map(({ retailerName, color }) => {
          const isHoveredLine = hoveredPoint?.retailerName === retailerName;
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
