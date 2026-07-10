import { useNavigate } from 'react-router-dom';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { PriorityIcon } from '@/components/PriorityIcon';
import { StoryPoints } from '@/components/StoryPoints';
import { UserAvatar } from '@/components/UserAvatar';
import { LabelBadge } from '@/features/issues/LabelBadge';
import type { Issue } from '@/features/issues/types';
import { cn } from '@/lib/utils';

interface IssueCardProps {
  issue: Issue;
  projectId: number | string;
  /** Rendu pendant le drag (ombre portée). */
  overlay?: boolean;
  /** Empêche la navigation quand la carte sert de handle de drag. */
  draggable?: boolean;
}

/** Carte de ticket du board (JIR-41). */
export function IssueCard({
  issue,
  projectId,
  overlay,
  draggable,
}: IssueCardProps) {
  const navigate = useNavigate();

  return (
    <div
      className={cn(
        'space-y-2 rounded-md border border-border bg-background p-3 text-sm shadow-sm',
        overlay && 'rotate-1 shadow-lg',
        !draggable && 'cursor-pointer hover:border-primary'
      )}
      onClick={
        draggable
          ? undefined
          : () => navigate(`/projects/${projectId}/issues/${issue.key}`)
      }
    >
      <p className="font-medium leading-snug">{issue.summary}</p>

      {issue.labels.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {issue.labels.map((l) => (
            <LabelBadge key={l.id} label={l} />
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <IssueTypeBadge type={issue.type} showLabel={false} />
        <span className="font-mono text-xs text-muted-foreground">
          {issue.key}
        </span>
        <PriorityIcon priority={issue.priority} />
        {issue.story_points != null && (
          <StoryPoints points={issue.story_points} />
        )}
        <span className="ml-auto">
          {issue.assignee && (
            <UserAvatar
              name={issue.assignee.full_name || issue.assignee.email}
              src={issue.assignee.avatar_url}
              size="sm"
            />
          )}
        </span>
      </div>
    </div>
  );
}
