import { useNavigate } from 'react-router-dom';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { StoryPoints } from '@/components/StoryPoints';
import { UserAvatar } from '@/components/UserAvatar';
import type { Issue } from '@/features/issues/types';
import { cn } from '@/lib/utils';

interface Props {
  issue: Issue;
  projectId: number | string;
  disabled?: boolean;
}

/** Ligne de ticket draggable pour le backlog (clic = ouvrir, drag = déplacer). */
export function SortableBacklogRow({ issue, projectId, disabled }: Props) {
  const navigate = useNavigate();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: String(issue.id),
      data: { issue },
      disabled,
    });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.4 : 1,
      }}
      className={cn(
        'flex items-center gap-2 rounded border border-border bg-background px-2 py-1.5 text-sm',
        !disabled && 'touch-none'
      )}
    >
      {!disabled && (
        <span
          {...attributes}
          {...listeners}
          className="cursor-grab text-muted-foreground"
          aria-label="Déplacer"
        >
          <GripVertical className="h-4 w-4" />
        </span>
      )}
      <IssueTypeBadge type={issue.type} showLabel={false} />
      <button
        type="button"
        onClick={() => navigate(`/projects/${projectId}/issues/${issue.key}`)}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
      >
        <span className="font-mono text-xs text-muted-foreground">
          {issue.key}
        </span>
        <span className="truncate hover:text-primary hover:underline">
          {issue.summary}
        </span>
      </button>
      <StatusBadge status={issue.status} />
      {issue.story_points != null && <StoryPoints points={issue.story_points} />}
      {issue.assignee && (
        <UserAvatar
          name={issue.assignee.full_name || issue.assignee.email}
          src={issue.assignee.avatar_url}
          size="sm"
        />
      )}
    </div>
  );
}
