import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { arrayMove } from '@dnd-kit/sortable';

import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ErrorState } from '@/components/ErrorState';
import { BoardSkeleton } from '@/components/LoadingSkeletons';
import { BoardColumnView } from '@/features/board/BoardColumnView';
import { IssueCard } from '@/features/board/IssueCard';
import { fetchBoard, moveIssue } from '@/features/board/api';
import { fetchSprints } from '@/features/sprints/api';
import type { Issue, IssueFilters } from '@/features/issues/types';
import { EmptyState } from '@/components/EmptyState';
import { useProject } from '@/features/projects/useProject';
import { usePersistedState } from '@/hooks/usePersistedState';
import {
  ISSUE_STATUSES,
  ISSUE_TYPE_META,
  ISSUE_TYPES,
  STATUS_META,
  type IssueStatus,
} from '@/lib/issues';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const ALL = 'all';
type Grouping = 'none' | 'epic' | 'assignee';
type ColsState = Record<IssueStatus, Issue[]>;

function buildCols(columns: { status: IssueStatus; issues: Issue[] }[]): ColsState {
  const cols = {} as ColsState;
  for (const s of ISSUE_STATUSES) cols[s] = [];
  for (const c of columns) cols[c.status] = c.issues;
  return cols;
}

export default function BoardPage() {
  const { project } = useProject();
  const canEdit = project.my_role === 'admin' || project.my_role === 'member';
  const queryClient = useQueryClient();

  const [prefs, setPrefs] = usePersistedState(`jirou.board.${project.id}`, {
    type: ALL,
    assignee: ALL,
    grouping: 'none' as Grouping,
    mode: 'kanban' as 'kanban' | 'scrum',
  });
  const [search, setSearch] = useState('');

  const sprintsQuery = useQuery({
    queryKey: queryKeys.sprints.list(project.id),
    queryFn: () => fetchSprints(project.id),
  });
  const activeSprint = sprintsQuery.data?.find((s) => s.status === 'active');
  const scrum = prefs.mode === 'scrum';

  const filters: IssueFilters = {
    search: search.trim() || undefined,
    type: prefs.type === ALL ? undefined : (prefs.type as IssueFilters['type']),
    assignee_id: prefs.assignee === ALL ? undefined : prefs.assignee,
    sprint_id: scrum ? activeSprint?.id : undefined,
  };

  const query = useQuery({
    queryKey: queryKeys.board.view(project.id, filters as Record<string, unknown>),
    queryFn: () => fetchBoard(project.id, filters),
    enabled: !scrum || !!activeSprint,
  });

  const [cols, setCols] = useState<ColsState>(() => ({}) as ColsState);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ColsState | null>(null);

  // Synchronise l'état local depuis le serveur hors drag.
  useEffect(() => {
    if (query.data && !activeId) setCols(buildCols(query.data.columns));
  }, [query.data, activeId]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const mutation = useMutation({
    mutationFn: (v: { key: string; status: IssueStatus; position: number }) =>
      moveIssue(v.key, { status: v.status, position: v.position }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.board.all }),
    onError: (err) => {
      toast.error('Déplacement échoué', getErrorMessage(err));
      queryClient.invalidateQueries({ queryKey: queryKeys.board.all });
    },
  });

  function findContainer(id: string): IssueStatus | null {
    if ((ISSUE_STATUSES as readonly string[]).includes(id)) return id as IssueStatus;
    for (const s of ISSUE_STATUSES) {
      if (cols[s]?.some((i) => String(i.id) === id)) return s;
    }
    return null;
  }

  const activeIssue = activeId
    ? ISSUE_STATUSES.flatMap((s) => cols[s] ?? []).find(
        (i) => String(i.id) === activeId
      )
    : undefined;

  function handleDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
    setSnapshot(cols);
  }

  function handleDragOver(e: DragOverEvent) {
    const { active, over } = e;
    if (!over) return;
    const activeIdStr = String(active.id);
    const overId = String(over.id);
    const from = findContainer(activeIdStr);
    const to = findContainer(overId);
    if (!from || !to || from === to) return;

    setCols((prev) => {
      const fromItems = prev[from];
      const toItems = prev[to];
      const item = fromItems.find((i) => String(i.id) === activeIdStr);
      if (!item) return prev;
      const overIndex = (ISSUE_STATUSES as readonly string[]).includes(overId)
        ? toItems.length
        : toItems.findIndex((i) => String(i.id) === overId);
      const insertAt = overIndex < 0 ? toItems.length : overIndex;
      const nextTo = [...toItems];
      nextTo.splice(insertAt, 0, item);
      return {
        ...prev,
        [from]: fromItems.filter((i) => String(i.id) !== activeIdStr),
        [to]: nextTo,
      };
    });
  }

  function handleDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    setActiveId(null);
    if (!over) return;
    const activeIdStr = String(active.id);
    const overId = String(over.id);
    const container = findContainer(overId);
    if (!container) return;

    const items = cols[container];
    const oldIndex = items.findIndex((i) => String(i.id) === activeIdStr);
    if (oldIndex === -1) return;
    let newIndex = (ISSUE_STATUSES as readonly string[]).includes(overId)
      ? items.length - 1
      : items.findIndex((i) => String(i.id) === overId);
    if (newIndex < 0) newIndex = items.length - 1;

    const reordered =
      oldIndex === newIndex ? items : arrayMove(items, oldIndex, newIndex);
    setCols((prev) => ({ ...prev, [container]: reordered }));

    const issue = items[oldIndex];
    mutation.mutate({ key: issue.key, status: container, position: newIndex });
  }

  function handleDragCancel() {
    if (snapshot) setCols(snapshot);
    setActiveId(null);
  }

  const allIssues = useMemo(
    () => (query.data ? query.data.columns.flatMap((c) => c.issues) : []),
    [query.data]
  );

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Rechercher…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select
          value={prefs.type}
          onValueChange={(v) => setPrefs((p) => ({ ...p, type: v }))}
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous types</SelectItem>
            {ISSUE_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {ISSUE_TYPE_META[t].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={prefs.assignee}
          onValueChange={(v) => setPrefs((p) => ({ ...p, assignee: v }))}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous assignés</SelectItem>
            {project.members.map((m) => (
              <SelectItem key={m.user_id} value={String(m.user_id)}>
                {m.user.full_name || m.user.email}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={prefs.grouping}
          onValueChange={(v) =>
            setPrefs((p) => ({ ...p, grouping: v as Grouping }))
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Sans regroupement</SelectItem>
            <SelectItem value="epic">Swimlanes par Epic</SelectItem>
            <SelectItem value="assignee">Swimlanes par assigné</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={prefs.mode}
          onValueChange={(v) =>
            setPrefs((p) => ({ ...p, mode: v as 'kanban' | 'scrum' }))
          }
        >
          <SelectTrigger className="w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="kanban">Kanban</SelectItem>
            <SelectItem value="scrum">Scrum</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {scrum && activeSprint && (
        <div className="rounded-md border border-border bg-surface px-4 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{activeSprint.name}</span>
            {activeSprint.end_date && (
              <span className="text-xs text-muted-foreground">
                fin le {activeSprint.end_date}
              </span>
            )}
          </div>
          {activeSprint.goal && (
            <p className="text-sm text-muted-foreground">{activeSprint.goal}</p>
          )}
        </div>
      )}

      {scrum && !activeSprint && (
        <EmptyState
          title="Aucun sprint actif"
          description="Démarrez un sprint depuis l'onglet Backlog pour utiliser le board Scrum."
        />
      )}

      {query.isLoading && <BoardSkeleton />}
      {query.isError && (
        <ErrorState
          description="Impossible de charger le board."
          onRetry={() => query.refetch()}
        />
      )}

      {query.data &&
        (prefs.grouping !== 'none' || !canEdit ? (
          <ReadOnlyBoard
            issues={allIssues}
            grouping={canEdit ? prefs.grouping : 'none'}
            projectId={project.id}
          />
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDragEnd={handleDragEnd}
            onDragCancel={handleDragCancel}
          >
            <div className="flex flex-1 gap-3 overflow-x-auto pb-2">
              {ISSUE_STATUSES.map((status) => (
                <BoardColumnView
                  key={status}
                  status={status}
                  issues={cols[status] ?? []}
                  projectId={project.id}
                />
              ))}
            </div>
            <DragOverlay>
              {activeIssue ? (
                <IssueCard
                  issue={activeIssue}
                  projectId={project.id}
                  overlay
                  draggable
                />
              ) : null}
            </DragOverlay>
          </DndContext>
        ))}
    </div>
  );
}

/** Vue lecture seule : colonnes simples, ou swimlanes groupées (JIR-45). */
function ReadOnlyBoard({
  issues,
  grouping,
  projectId,
}: {
  issues: Issue[];
  grouping: Grouping;
  projectId: number | string;
}) {
  const epicLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const i of issues) {
      if (i.type === 'epic') map.set(String(i.id), `${i.key} · ${i.summary}`);
    }
    return map;
  }, [issues]);

  const lanes = useMemo(() => {
    if (grouping === 'none') return [{ key: 'all', label: '', issues }];
    const groups = new Map<string, { label: string; issues: Issue[] }>();
    for (const i of issues) {
      let k: string;
      let label: string;
      if (grouping === 'epic') {
        k = i.epic_id ? String(i.epic_id) : 'none';
        label = i.epic_id ? (epicLabel.get(String(i.epic_id)) ?? 'Epic') : 'Sans epic';
      } else {
        k = i.assignee_id ? String(i.assignee_id) : 'none';
        label = i.assignee ? i.assignee.full_name || i.assignee.email : 'Non assigné';
      }
      if (!groups.has(k)) groups.set(k, { label, issues: [] });
      groups.get(k)!.issues.push(i);
    }
    return [...groups.entries()].map(([key, v]) => ({ key, ...v }));
  }, [issues, grouping, epicLabel]);

  return (
    <div className="flex flex-col gap-6 overflow-x-auto pb-2">
      {lanes.map((lane) => (
        <div key={lane.key}>
          {lane.label && (
            <h3 className="mb-2 text-sm font-semibold">{lane.label}</h3>
          )}
          <div className="flex gap-3">
            {ISSUE_STATUSES.map((status) => {
              const colIssues = lane.issues.filter((i) => i.status === status);
              return (
                <div
                  key={status}
                  className="flex w-72 shrink-0 flex-col rounded-lg bg-surface"
                >
                  <header className="flex items-center gap-2 px-3 py-2">
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ backgroundColor: STATUS_META[status].color }}
                    />
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {STATUS_META[status].label}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {colIssues.length}
                    </span>
                  </header>
                  <div className="flex min-h-16 flex-col gap-2 p-2">
                    {colIssues.map((issue) => (
                      <IssueCard
                        key={issue.id}
                        issue={issue}
                        projectId={projectId}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
