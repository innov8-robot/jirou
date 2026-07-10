import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bookmark, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { createView, deleteView, fetchViews } from './api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

interface Props {
  projectId: number | string;
  currentFilters: Record<string, unknown>;
  onApply: (filters: Record<string, unknown>) => void;
}

export function SavedViewsControl({ projectId, currentFilters, onApply }: Props) {
  const queryClient = useQueryClient();
  const [saveOpen, setSaveOpen] = useState(false);
  const [name, setName] = useState('');

  const { data: views = [] } = useQuery({
    queryKey: queryKeys.views.list(projectId),
    queryFn: () => fetchViews(projectId),
  });
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.views.list(projectId) });

  const saveMutation = useMutation({
    mutationFn: () => createView(projectId, { name: name.trim(), filters: currentFilters }),
    onSuccess: () => {
      invalidate();
      toast.success('Vue enregistrée');
      setSaveOpen(false);
      setName('');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteView(id),
    onSuccess: invalidate,
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm">
            <Bookmark className="h-4 w-4" />
            Vues{views.length ? ` (${views.length})` : ''}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>Vues sauvegardées</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {views.length === 0 && (
            <DropdownMenuItem disabled>Aucune vue</DropdownMenuItem>
          )}
          {views.map((v) => (
            <DropdownMenuItem
              key={v.id}
              onSelect={() => onApply(v.filters)}
              className="flex items-center gap-2"
            >
              <span className="flex-1 truncate">{v.name}</span>
              <button
                type="button"
                aria-label={`Supprimer ${v.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  deleteMutation.mutate(v.id);
                }}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setSaveOpen(true)}>
            Enregistrer la vue actuelle…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enregistrer la vue</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (name.trim()) saveMutation.mutate();
            }}
          >
            <Input
              placeholder="Nom de la vue"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <DialogFooter className="mt-4">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setSaveOpen(false)}
              >
                Annuler
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                Enregistrer
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
