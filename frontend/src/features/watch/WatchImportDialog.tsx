import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { importWatchArchive, type WatchImportResult } from './api';
import { useAuth } from '@/features/auth/useAuth';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

/**
 * Import d'une archive de veille (ZIP produit par « Exporter », ou manifeste
 * `veille.json` nu). Deux modes : additif (défaut) ou remplacement complet —
 * ce dernier n'est proposé qu'aux admins globaux (et revérifié côté serveur).
 */
export function WatchImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { isAdmin } = useAuth();

  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(false);
  const [result, setResult] = useState<WatchImportResult | null>(null);

  const mutation = useMutation({
    mutationFn: () => importWatchArchive(file!, replace && isAdmin),
    onSuccess: (res) => {
      setResult(res);
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
      toast.success(`${res.nodes_created} nœud(s) importé(s)`);
    },
    onError: (err) => toast.error('Import échoué', getErrorMessage(err)),
  });

  function close(o: boolean) {
    onOpenChange(o);
    if (!o) {
      setFile(null);
      setReplace(false);
      setResult(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Importer une veille</DialogTitle>
          <DialogDescription>
            Reprenez une archive exportée depuis Jirou (arbre, notes, liens,
            commentaires et fichiers).
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <div className="min-w-0 space-y-4">
            <div className="space-y-1.5 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
              <p>
                Formats acceptés : l'archive{' '}
                <code className="rounded bg-background px-1">.zip</code> produite
                par « Exporter » (recommandé, fichiers inclus) ou son manifeste{' '}
                <code className="rounded bg-background px-1">veille.json</code>{' '}
                seul (sans les images/vidéos).
              </p>
              <p>
                Les nœuds dont le parent est introuvable sont importés comme
                thèmes racines ; un média illisible est ignoré et signalé.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label>Archive</Label>
              <input
                type="file"
                accept=".zip,.json,application/zip,application/json"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm"
              />
            </div>

            {isAdmin && (
              <label className="flex items-start gap-2 rounded-md border border-border p-3 text-sm">
                <input
                  type="checkbox"
                  checked={replace}
                  onChange={(e) => setReplace(e.target.checked)}
                  className="mt-0.5 h-4 w-4 accent-destructive"
                />
                <span>
                  Remplacer la veille existante
                  <span className="block text-xs text-destructive">
                    ⚠ supprime définitivement tous les nœuds actuels, leurs
                    médias et leurs commentaires.
                  </span>
                </span>
              </label>
            )}

            <DialogFooter>
              <Button variant="ghost" onClick={() => close(false)}>
                Annuler
              </Button>
              <Button
                disabled={!file || mutation.isPending}
                onClick={() => {
                  if (
                    replace &&
                    !confirm(
                      'Remplacer la veille existante ? Tous les nœuds actuels, leurs médias et leurs commentaires seront supprimés.'
                    )
                  )
                    return;
                  mutation.mutate();
                }}
              >
                <Upload className="h-4 w-4" />
                {mutation.isPending ? 'Import…' : 'Importer'}
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm">
              <span className="font-semibold text-status-done">
                {result.nodes_created}
              </span>{' '}
              nœud(s), {result.media_created} média(s) et{' '}
              {result.comments_created} commentaire(s) importé(s).
              {result.replaced && ' La veille précédente a été remplacée.'}
            </p>
            {result.errors.length > 0 && (
              <ul className="max-h-48 space-y-1 overflow-y-auto rounded border border-border p-2 text-xs">
                {result.errors.map((e, i) => (
                  <li key={i}>
                    {e.ref && (
                      <span className="font-mono text-muted-foreground">
                        {e.ref}
                      </span>
                    )}{' '}
                    — {e.message}
                  </li>
                ))}
              </ul>
            )}
            <DialogFooter>
              <Button onClick={() => close(false)}>Fermer</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
