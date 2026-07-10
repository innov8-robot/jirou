import { cn } from '@/lib/utils';
import { PRIORITY_META, type Priority } from '@/lib/issues';

interface PriorityIconProps {
  priority: Priority;
  /** Show the text label next to the icon (default: false). */
  showLabel?: boolean;
  className?: string;
}

/**
 * Arrow icon conveying an issue priority (Highest → Lowest), colored per
 * {@link PRIORITY_META}. Renders label-less by default (table/board usage);
 * pass `showLabel` for forms and detail views.
 */
export function PriorityIcon({
  priority,
  showLabel = false,
  className,
}: PriorityIconProps) {
  const meta = PRIORITY_META[priority];
  const Icon = meta.icon;

  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-sm', className)}
      data-priority={priority}
      title={meta.label}
    >
      <Icon
        className="h-4 w-4"
        style={{ color: meta.color }}
        aria-hidden="true"
      />
      {showLabel ? (
        <span className="text-foreground">{meta.label}</span>
      ) : (
        <span className="sr-only">{meta.label}</span>
      )}
    </span>
  );
}
