import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { PriorityIcon } from '@/components/PriorityIcon';
import { fetchProjects } from '@/features/projects/api';
import { createIssue } from '@/features/issues/api';
import {
  ISSUE_TYPES,
  PRIORITIES,
  type IssueType,
  type Priority,
} from '@/lib/issues';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';
import { useUiStore } from '@/stores/uiStore';

const EMPTY_FORM = {
  projectId: '',
  type: 'story' as IssueType,
  priority: 'medium' as Priority,
  summary: '',
  description: '',
};

/**
 * Global "quick create" issue modal (JIR-21) — branchée sur l'API (EPIC-05).
 * Ouverture pilotée par le store UI (bouton « Créer » + raccourci `c`).
 */
export function CreateIssueModal() {
  const isOpen = useUiStore((s) => s.isCreateIssueOpen);
  const setOpen = useUiStore((s) => s.setCreateIssueOpen);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY_FORM);

  const { data: projects = [] } = useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => fetchProjects(false),
    enabled: isOpen,
  });

  const mutation = useMutation({
    mutationFn: () =>
      createIssue(form.projectId, {
        type: form.type,
        summary: form.summary.trim(),
        description: form.description.trim() || undefined,
        priority: form.priority,
      }),
    onSuccess: (issue) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
      toast.success('Ticket créé', issue.key);
      reset();
      setOpen(false);
      navigate(`/projects/${issue.project_id}/issues/${issue.key}`);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const canSubmit = form.projectId !== '' && form.summary.trim() !== '';

  function reset() {
    setForm(EMPTY_FORM);
  }

  function handleOpenChange(open: boolean) {
    setOpen(open);
    if (!open) reset();
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (canSubmit) mutation.mutate();
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Créer un ticket</DialogTitle>
          <DialogDescription>
            Choisissez un projet et décrivez le ticket.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <Label htmlFor="issue-project">Projet</Label>
            <Select
              value={form.projectId}
              onValueChange={(projectId) =>
                setForm((f) => ({ ...f, projectId }))
              }
            >
              <SelectTrigger id="issue-project" aria-label="Projet">
                <SelectValue placeholder="Sélectionner un projet…" />
              </SelectTrigger>
              <SelectContent>
                {projects.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name} ({p.key})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="issue-type">Type</Label>
              <Select
                value={form.type}
                onValueChange={(type) =>
                  setForm((f) => ({ ...f, type: type as IssueType }))
                }
              >
                <SelectTrigger id="issue-type" aria-label="Type de ticket">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ISSUE_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      <IssueTypeBadge type={t} />
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="issue-priority">Priorité</Label>
              <Select
                value={form.priority}
                onValueChange={(priority) =>
                  setForm((f) => ({ ...f, priority: priority as Priority }))
                }
              >
                <SelectTrigger id="issue-priority" aria-label="Priorité">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      <span className="flex items-center gap-2">
                        <PriorityIcon priority={p} showLabel />
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="issue-summary">Résumé</Label>
            <Input
              id="issue-summary"
              placeholder="Ex. : Le bouton de connexion ne répond pas"
              value={form.summary}
              onChange={(e) =>
                setForm((f) => ({ ...f, summary: e.target.value }))
              }
              required
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="issue-description">Description</Label>
            <Textarea
              id="issue-description"
              placeholder="Ajouter plus de détails…"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => handleOpenChange(false)}
            >
              Annuler
            </Button>
            <Button type="submit" disabled={!canSubmit || mutation.isPending}>
              {mutation.isPending ? 'Création…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
