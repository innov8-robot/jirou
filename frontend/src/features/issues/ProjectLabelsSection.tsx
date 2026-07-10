import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LabelBadge } from './LabelBadge';
import { createLabel, deleteLabel, fetchLabels } from './api';
import { PROJECT_COLORS } from '@/features/projects/colors';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

export function ProjectLabelsSection({
  projectId,
  canEdit,
}: {
  projectId: number | string;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.labels.list(projectId),
    });

  const { data: labels = [] } = useQuery({
    queryKey: queryKeys.labels.list(projectId),
    queryFn: () => fetchLabels(projectId),
  });

  const [name, setName] = useState('');
  const [color, setColor] = useState<string>(PROJECT_COLORS[0]);

  const addMutation = useMutation({
    mutationFn: () => createLabel(projectId, { name: name.trim(), color }),
    onSuccess: () => {
      invalidate();
      toast.success('Label créé');
      setName('');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const removeMutation = useMutation({
    mutationFn: (id: number) => deleteLabel(id),
    onSuccess: () => {
      invalidate();
      toast.success('Label supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function handleAdd(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) addMutation.mutate();
  }

  return (
    <section className="rounded-lg border border-border p-6">
      <h2 className="mb-4 text-lg font-semibold">Labels</h2>

      <div className="mb-4 flex flex-wrap gap-2">
        {labels.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucun label.</p>
        )}
        {labels.map((l) => (
          <span key={l.id} className="inline-flex items-center gap-1">
            <LabelBadge label={l} />
            {canEdit && (
              <button
                type="button"
                aria-label={`Supprimer ${l.name}`}
                onClick={() => removeMutation.mutate(l.id)}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))}
      </div>

      {canEdit && (
        <form className="flex flex-wrap items-center gap-2" onSubmit={handleAdd}>
          <Input
            placeholder="Nom du label"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="max-w-xs"
          />
          <div className="flex gap-1">
            {PROJECT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`Couleur ${c}`}
                onClick={() => setColor(c)}
                className={cn(
                  'h-6 w-6 rounded-full ring-offset-2 ring-offset-background',
                  color === c && 'ring-2 ring-foreground'
                )}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <Button type="submit" disabled={addMutation.isPending}>
            Ajouter
          </Button>
        </form>
      )}
    </section>
  );
}
