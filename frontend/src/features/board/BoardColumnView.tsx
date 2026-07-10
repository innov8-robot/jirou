import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';

import { SortableIssueCard } from './SortableIssueCard';
import type { Issue } from '@/features/issues/types';
import { STATUS_META, type IssueStatus } from '@/lib/issues';

interface BoardColumnViewProps {
  status: IssueStatus;
  issues: Issue[];
  projectId: number | string;
}

/** Colonne de statut droppable contenant des cartes sortables. */
export function BoardColumnView({
  status,
  issues,
  projectId,
}: BoardColumnViewProps) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const meta = STATUS_META[status];

  return (
    <div className="flex w-72 shrink-0 flex-col rounded-lg bg-surface">
      <header className="flex items-center gap-2 px-3 py-2">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: meta.color }}
        />
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {meta.label}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          {issues.length}
        </span>
      </header>
      <SortableContext
        items={issues.map((i) => String(i.id))}
        strategy={verticalListSortingStrategy}
      >
        <div
          ref={setNodeRef}
          className={`flex min-h-24 flex-1 flex-col gap-2 p-2 transition-colors ${
            isOver ? 'bg-primary/5' : ''
          }`}
        >
          {issues.map((issue) => (
            <SortableIssueCard
              key={issue.id}
              issue={issue}
              projectId={projectId}
              status={status}
            />
          ))}
          {issues.length === 0 && (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">
              Déposer ici
            </p>
          )}
        </div>
      </SortableContext>
    </div>
  );
}
