import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface ListSkeletonProps {
  /** Number of placeholder rows (default 5). */
  rows?: number;
  className?: string;
}

/** Placeholder for a vertical list of issues/rows while data loads. */
export function ListSkeleton({ rows = 5, className }: ListSkeletonProps) {
  return (
    <div className={cn('space-y-2', className)} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 rounded-md border border-border p-3"
        >
          <Skeleton className="h-5 w-5 rounded" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-6 w-6 rounded-full" />
        </div>
      ))}
    </div>
  );
}

interface BoardSkeletonProps {
  /** Number of columns (default 4, matching the fixed workflow). */
  columns?: number;
  /** Cards per column (default 3). */
  cardsPerColumn?: number;
  className?: string;
}

/** Placeholder for a Kanban board (columns of cards) while data loads. */
export function BoardSkeleton({
  columns = 4,
  cardsPerColumn = 3,
  className,
}: BoardSkeletonProps) {
  return (
    <div
      className={cn('flex gap-4 overflow-x-auto', className)}
      aria-hidden="true"
    >
      {Array.from({ length: columns }).map((_, col) => (
        <div
          key={col}
          className="flex w-72 shrink-0 flex-col gap-3 rounded-lg bg-surface p-3"
        >
          <Skeleton className="h-4 w-24" />
          {Array.from({ length: cardsPerColumn }).map((__, card) => (
            <div
              key={card}
              className="space-y-2 rounded-md border border-border bg-background p-3"
            >
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <div className="flex items-center justify-between pt-1">
                <Skeleton className="h-5 w-5 rounded" />
                <Skeleton className="h-6 w-6 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
