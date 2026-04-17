import { forwardRef } from 'react';

interface ResponsiveTableWrapperProps {
  visibleColumns: string[];
  columnMinWidths: Record<string, number>;
  totalMinWidth: number;
  tableClassName?: string;
  children: React.ReactNode;
}

/**
 * Wrapper that provides the measurement div (forwarded ref), horizontal-scroll
 * container, and a <colgroup> with proportional widths derived from columnMinWidths.
 * Pair with useContainerWidth + useResponsiveColumns.
 */
const ResponsiveTableWrapper = ({
  ref,
  visibleColumns,
  columnMinWidths,
  totalMinWidth,
  tableClassName = 'w-full text-sm table-fixed',
  children,
}: ResponsiveTableWrapperProps & { ref?: React.Ref<HTMLDivElement> }) => (
  <div ref={ref} className="min-w-0">
    <div className="overflow-x-auto min-w-0 rounded-inherit">
      <table className={tableClassName}>
        <colgroup>
          {visibleColumns.map((key) => (
            <col
              key={key}
              style={{
                width: `${(columnMinWidths[key] / totalMinWidth) * 100}%`,
              }}
            />
          ))}
        </colgroup>
        {children}
      </table>
    </div>
  </div>
);

ResponsiveTableWrapper.displayName = 'ResponsiveTableWrapper';

export default ResponsiveTableWrapper;
