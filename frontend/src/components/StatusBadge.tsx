import { cn } from '@/lib/utils';
import { STATUS_META, type IssueStatus } from '@/lib/issues';

interface StatusBadgeProps {
  status: IssueStatus;
  className?: string;
}

/**
 * Pill showing a workflow status (To Do / In Progress / In Review / Done)
 * with the conventional status color. Colors come from {@link STATUS_META}.
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const meta = STATUS_META[status];

  return (
    <span
      data-status={status}
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide',
        meta.className,
        className
      )}
    >
      {meta.label}
    </span>
  );
}
