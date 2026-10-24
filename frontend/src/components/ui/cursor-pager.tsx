import * as React from 'react';

import { cn } from '../../lib/utils';
import { Button } from './button';

/** Props for CursorPager: the current page number and whether more follow. */
export interface CursorPagerProps {
  currentPage: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
  className?: string;
}

/** Previous and next controls for a cursor paged list. */
const CursorPager: React.FC<CursorPagerProps> = ({
  currentPage,
  hasNext,
  onPageChange,
  className,
}) => {
  if (currentPage <= 1 && !hasNext) {
    return null;
  }

  return (
    <div
      className={cn('mt-8 flex items-center justify-center gap-4', className)}
    >
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        aria-label="Previous page"
      >
        Previous
      </Button>
      <span className="text-sm text-muted-foreground">Page {currentPage}</span>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={!hasNext}
        aria-label="Next page"
      >
        Next
      </Button>
    </div>
  );
};

export default CursorPager;
