import { cn } from '@/lib/utils';
import { ISSUE_TYPE_META, type IssueType } from '@/lib/issues';

interface IssueTypeBadgeProps {
  type: IssueType;
  /** Show the text label next to the icon (default: true). */
  showLabel?: boolean;
  className?: string;
}

/**
 * Colored, icon-led badge identifying an issue type (Epic / Story / Task /
 * Bug). The icon sits on a tinted square filled with the type color, à la
 * Jira. Colors come from {@link ISSUE_TYPE_META}.
 */
export function IssueTypeBadge({
  type,
  showLabel = true,
  className,
}: IssueTypeBadgeProps) {
  const meta = ISSUE_TYPE_META[type];
  const Icon = meta.icon;

  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-sm', className)}
      data-issue-type={type}
    >
      <span
        className="flex h-5 w-5 items-center justify-center rounded"
        style={{ backgroundColor: meta.color }}
        aria-hidden="true"
      >
        <Icon className="h-3.5 w-3.5 text-white" />
      </span>
      {showLabel && <span className="text-foreground">{meta.label}</span>}
      {!showLabel && <span className="sr-only">{meta.label}</span>}
    </span>
  );
}
