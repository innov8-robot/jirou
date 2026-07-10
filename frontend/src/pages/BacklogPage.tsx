import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { SortableBacklogRow } from '@/features/sprints/SortableBacklogRow';
import {
  StartSprintDialog,
  CompleteSprintDialog,
} from '@/features/sprints/SprintDialogs';
import { VelocityChart } from '@/features/sprints/VelocityChart';
import {
  backlogMove,
  createSprint,
  deleteSprint,
  fetchBacklog,
} from '@/features/sprints/api';
import type { BacklogData, Sprint } from '@/features/sprints/types';
import type { Issue } from '@/features/issues/types';
import { useProject } from '@/features/projects/useProject';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const BACKLOG = 'backlog';
const bucketOf = (sprintId: number | string) => `s:${sprintId}`;
const sprintIdOf = (bucket: string): number | string | null =>
  bucket === BACKLOG ? null : bucket.slice(2);

interface BuiltState {
  buckets: Record<string, Issue[]>;
  order: string[];
  sprints: Record<string, Sprint>;
}

function build(data: BacklogData): BuiltState {
  const buckets: Record<string, Issue[]> = {};
  const sprints: Record<string, Sprint> = {};
  const order: string[] = [];
  for (const s of data.sprints) {
    const id = bucketOf(s.sprint.id);
    buckets[id] = s.issues;
    sprints[id] = s.sprint;
    order.push(id);
  }
  buckets[BACKLOG] = data.backlog.issues;
  order.push(BACKLOG);
  return { buckets, order, sprints };
}

const sumPoints = (issues: Issue[]) =>
  issues.reduce((acc, i) => acc + (i.story_points ?? 0), 0);

export default function BacklogPage() {
  const { project } = useProject();
  const canEdit = project.my_role === 'admin' || project.my_role === 'member';
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.backlog.view(project.id),
    queryFn: () => fetchBacklog(project.id),
  });

  const [state, setState] = useState<BuiltState>({
    buckets: {},
    order: [],
    sprints: {},
  });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [startSprint, setStartSprint] = useState<Sprint | null>(null);
  const [completeSprintTarget, setCompleteSprintTarget] =
    useState<Sprint | null>(null);

  useEffect(() => {
    if (query.data && !activeId) setState(build(query.data));
  }, [query.data, activeId]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const moveMutation = useMutation({
    mutationFn: (v: {
      key: string;
      sprint_id: number | string | null;
      position: number;
    }) => backlogMove(v.key, { sprint_id: v.sprint_id, position: v.position }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.backlog.all }),
    onError: (err) => {
      toast.error('Déplacement échoué', getErrorMessage(err));
      queryClient.invalidateQueries({ queryKey: queryKeys.backlog.all });
    },
  });

  function findContainer(id: string): string | null {
    if (state.buckets[id]) return id;
    for (const b of state.order) {
      if (state.buckets[b]?.some((i) => String(i.id) === id)) return b;
    }
    return null;
  }

  function handleDragOver(e: DragOverEvent) {
    const { active, over } = e;
    if (!over) return;
    const activeIdStr = String(active.id);
    const overId = String(over.id);
    const from = findContainer(activeIdStr);
    const to = findContainer(overId);
    if (!from || !to || from === to) return;
    setState((prev) => {
      const fromItems = prev.buckets[from];
      const toItems = prev.buckets[to];
      const item = fromItems.find((i) => String(i.id) === activeIdStr);
      if (!item) return prev;
      const overIndex = prev.buckets[overId]
        ? toItems.length
        : toItems.findIndex((i) => String(i.id) === overId);
      const insertAt = overIndex < 0 ? toItems.length : overIndex;
      const nextTo = [...toItems];
      nextTo.splice(insertAt, 0, item);
      return {
        ...prev,
        buckets: {
          ...prev.buckets,
          [from]: fromItems.filter((i) => String(i.id) !== activeIdStr),
          [to]: nextTo,
        },
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
    const items = state.buckets[container];
    const oldIndex = items.findIndex((i) => String(i.id) === activeIdStr);
    if (oldIndex === -1) return;
    let newIndex = state.buckets[overId]
      ? items.length - 1
      : items.findIndex((i) => String(i.id) === overId);
    if (newIndex < 0) newIndex = items.length - 1;
    const reordered =
      oldIndex === newIndex ? items : arrayMove(items, oldIndex, newIndex);
    setState((prev) => ({
      ...prev,
      buckets: { ...prev.buckets, [container]: reordered },
    }));
    const issue = items[oldIndex];
    moveMutation.mutate({
      key: issue.key,
      sprint_id: sprintIdOf(container),
      position: newIndex,
    });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: number | string) => deleteSprint(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.backlog.all });
      toast.success('Sprint supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  if (query.isLoading) {
    return (
      <div className="p-6">
        <ListSkeleton />
      </div>
    );
  }
  if (query.isError) {
    return (
      <div className="p-6">
        <ErrorState
          description="Impossible de charger le backlog."
          onRetry={() => query.refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={(e) => setActiveId(String(e.active.id))}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveId(null)}
      >
        {state.order.map((bucketId) => {
          const sprint = state.sprints[bucketId];
          const issues = state.buckets[bucketId] ?? [];
          return (
            <Bucket
              key={bucketId}
              bucketId={bucketId}
              issues={issues}
              projectId={project.id}
              canEdit={canEdit}
              sprint={sprint}
              onStart={() => sprint && setStartSprint(sprint)}
              onComplete={() => sprint && setCompleteSprintTarget(sprint)}
              onDelete={() => sprint && deleteMutation.mutate(sprint.id)}
              onCreateSprint={() => setCreateOpen(true)}
            />
          );
        })}
      </DndContext>

      <VelocityChart projectId={project.id} />

      {createOpen && (
        <CreateSprintDialog
          projectId={project.id}
          open={createOpen}
          onOpenChange={setCreateOpen}
        />
      )}
      {startSprint && (
        <StartSprintDialog
          sprint={startSprint}
          open={!!startSprint}
          onOpenChange={(o) => !o && setStartSprint(null)}
        />
      )}
      {completeSprintTarget && (
        <CompleteSprintDialog
          sprint={completeSprintTarget}
          open={!!completeSprintTarget}
          onOpenChange={(o) => !o && setCompleteSprintTarget(null)}
        />
      )}
    </div>
  );
}

function Bucket({
  bucketId,
  issues,
  projectId,
  canEdit,
  sprint,
  onStart,
  onComplete,
  onDelete,
  onCreateSprint,
}: {
  bucketId: string;
  issues: Issue[];
  projectId: number | string;
  canEdit: boolean;
  sprint?: Sprint;
  onStart: () => void;
  onComplete: () => void;
  onDelete: () => void;
  onCreateSprint: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: bucketId });
  const isBacklog = bucketId === BACKLOG;

  return (
    <section className="rounded-lg border border-border">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
        <h2 className="font-semibold">{isBacklog ? 'Backlog' : sprint?.name}</h2>
        {sprint && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              sprint.status === 'active'
                ? 'bg-primary/15 text-primary'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            {sprint.status === 'active' ? 'actif' : 'à venir'}
          </span>
        )}
        <span className="text-xs text-muted-foreground">
          {issues.length} ticket{issues.length > 1 ? 's' : ''} ·{' '}
          {sumPoints(issues)} pts
        </span>

        <div className="ml-auto flex items-center gap-2">
          {canEdit && sprint?.status === 'future' && (
            <>
              <Button size="sm" onClick={onStart}>
                Démarrer
              </Button>
              <Button size="sm" variant="ghost" onClick={onDelete}>
                Supprimer
              </Button>
            </>
          )}
          {sprint?.status === 'active' && (
            <>
              <Button size="sm" variant="outline" asChild>
                <Link to={`/projects/${projectId}/board`}>Board</Link>
              </Button>
              {canEdit && (
                <Button size="sm" onClick={onComplete}>
                  Clôturer
                </Button>
              )}
            </>
          )}
          {isBacklog && canEdit && (
            <Button size="sm" variant="outline" onClick={onCreateSprint}>
              <Plus className="h-4 w-4" />
              Créer un sprint
            </Button>
          )}
        </div>
      </header>

      <SortableContext
        items={issues.map((i) => String(i.id))}
        strategy={verticalListSortingStrategy}
      >
        <div
          ref={setNodeRef}
          className={`flex min-h-16 flex-col gap-1.5 p-2 transition-colors ${
            isOver ? 'bg-primary/5' : ''
          }`}
        >
          {issues.map((issue) => (
            <SortableBacklogRow
              key={issue.id}
              issue={issue}
              projectId={projectId}
              disabled={!canEdit}
            />
          ))}
          {issues.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-muted-foreground">
              {isBacklog ? 'Backlog vide' : 'Glissez des tickets ici'}
            </p>
          )}
        </div>
      </SortableContext>
    </section>
  );
}

function CreateSprintDialog({
  projectId,
  open,
  onOpenChange,
}: {
  projectId: number | string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      createSprint(projectId, { name: name.trim(), goal: goal.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.backlog.all });
      qc.invalidateQueries({ queryKey: queryKeys.sprints.list(projectId) });
      toast.success('Sprint créé');
      onOpenChange(false);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) mutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau sprint</DialogTitle>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-1.5">
            <Label htmlFor="sprint_name">Nom</Label>
            <Input
              id="sprint_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Sprint 1"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sprint_goal">Objectif</Label>
            <Textarea
              id="sprint_goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={2}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              Créer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
