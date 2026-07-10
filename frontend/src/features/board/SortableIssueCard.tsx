import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { IssueCard } from './IssueCard';
import type { Issue } from '@/features/issues/types';
import type { IssueStatus } from '@/lib/issues';

interface SortableIssueCardProps {
  issue: Issue;
  projectId: number | string;
  status: IssueStatus;
}

/** Carte draggable/sortable (dnd-kit) — JIR-43. */
export function SortableIssueCard({
  issue,
  projectId,
  status,
}: SortableIssueCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: String(issue.id), data: { status, issue } });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.4 : 1,
      }}
      {...attributes}
      {...listeners}
      className="touch-none"
    >
      <IssueCard issue={issue} projectId={projectId} draggable />
    </div>
  );
}
