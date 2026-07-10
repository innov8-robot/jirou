import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { completeSprint, startSprint } from './api';
import type { Sprint } from './types';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

function invalidateProject(
  qc: ReturnType<typeof useQueryClient>,
  projectId: number | string
) {
  qc.invalidateQueries({ queryKey: queryKeys.backlog.all });
  qc.invalidateQueries({ queryKey: queryKeys.sprints.list(projectId) });
  qc.invalidateQueries({ queryKey: queryKeys.board.all });
  qc.invalidateQueries({ queryKey: queryKeys.velocity.view(projectId) });
}

export function StartSprintDialog({
  sprint,
  open,
  onOpenChange,
}: {
  sprint: Sprint;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [start, setStart] = useState(sprint.start_date ?? '');
  const [end, setEnd] = useState(sprint.end_date ?? '');

  const mutation = useMutation({
    mutationFn: () =>
      startSprint(sprint.id, {
        start_date: start || null,
        end_date: end || null,
      }),
    onSuccess: () => {
      invalidateProject(qc, sprint.project_id);
      toast.success('Sprint démarré', sprint.name);
      onOpenChange(false);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Démarrer « {sprint.name} »</DialogTitle>
          <DialogDescription>
            Un seul sprint peut être actif à la fois.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="start">Début</Label>
            <Input
              id="start"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="end">Fin</Label>
            <Input
              id="end"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Démarrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CompleteSprintDialog({
  sprint,
  open,
  onOpenChange,
}: {
  sprint: Sprint;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const [moveTo, setMoveTo] = useState<'backlog' | 'next'>('backlog');

  const mutation = useMutation({
    mutationFn: () =>
      completeSprint(sprint.id, { move_incomplete_to: moveTo }),
    onSuccess: (res) => {
      invalidateProject(qc, sprint.project_id);
      toast.success(
        'Sprint clôturé',
        `${res.done_count} terminé(s) · ${res.not_done_count} déplacé(s)`
      );
      onOpenChange(false);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clôturer « {sprint.name} »</DialogTitle>
          <DialogDescription>
            Les tickets non terminés seront déplacés.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label>Tickets non terminés →</Label>
          <Select
            value={moveTo}
            onValueChange={(v) => setMoveTo(v as 'backlog' | 'next')}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="backlog">Backlog</SelectItem>
              <SelectItem value="next">Prochain sprint</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Clôturer le sprint
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
