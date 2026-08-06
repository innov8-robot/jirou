import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, Download, Upload } from 'lucide-react';

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
import { importWatchCsv, type WatchCsvImportResult } from './api';
import { AI_PROMPT, CSV_HEADER, downloadWatchCsvTemplate } from './csvTemplate';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

/**
 * Import CSV **ancré** : les nœuds décrits sont greffés sous `nodeId`.
 *
 * Le dialogue expose aussi le prompt à donner à une IA : c'est le vrai chemin
 * d'usage — on demande une recherche à un assistant, on récupère le CSV, on
 * l'importe sous le bon thème.
 */
export function WatchCsvImportDialog({
  nodeId,
  nodeTitle,
  open,
  onOpenChange,
}: {
  nodeId: number;
  nodeTitle: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<WatchCsvImportResult | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: () => importWatchCsv(nodeId, file!),
    onSuccess: (res) => {
      setResult(res);
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.node(nodeId) });
      toast.success(`${res.nodes_created} sous-nœud(s) créé(s)`);
    },
    onError: (err) => toast.error('Import échoué', getErrorMessage(err)),
  });

  function close(o: boolean) {
    onOpenChange(o);
    if (!o) {
      setFile(null);
      setResult(null);
      setCopied(false);
    }
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(AI_PROMPT);
      setCopied(true);
      toast.success('Prompt copié', 'Collez-le dans votre IA, suivi du sujet.');
    } catch {
      toast.error('Copie impossible', 'Sélectionnez le texte et copiez-le à la main.');
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Importer des sous-nœuds</DialogTitle>
          <DialogDescription>
            Les nœuds du CSV seront rattachés sous « {nodeTitle} ». Le reste de la
            veille n'est pas touché.
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <div className="min-w-0 space-y-4">
            <div className="min-w-0 space-y-1.5 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
              <p>Entête attendue :</p>
              <code className="block overflow-x-auto whitespace-nowrap rounded bg-background px-2 py-1 text-foreground">
                {CSV_HEADER}
              </code>
              <p>
                Seul <code className="rounded bg-background px-1">title</code> est
                obligatoire.{' '}
                <code className="rounded bg-background px-1">parent</code> reprend
                le <em>titre</em> d'une autre ligne du fichier — vide = enfant
                direct de « {nodeTitle} ».
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={downloadWatchCsvTemplate}>
                <Download className="h-4 w-4" />
                Modèle CSV
              </Button>
              <Button variant="outline" size="sm" onClick={copyPrompt}>
                {copied ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
                {copied ? 'Prompt copié' : 'Copier le prompt IA'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Le prompt demande à une IA de produire ce CSV : collez-le, ajoutez
              votre sujet à la fin, récupérez le fichier.
            </p>

            <div className="space-y-1.5">
              <Label>Fichier CSV</Label>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm"
              />
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={() => close(false)}>
                Annuler
              </Button>
              <Button
                disabled={!file || mutation.isPending}
                onClick={() => mutation.mutate()}
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
              sous-nœud(s) créé(s)
              {result.links_created > 0 && `, ${result.links_created} lien(s)`}.
              {result.error_count > 0 && (
                <>
                  {' '}
                  <span className="font-semibold text-destructive">
                    {result.error_count}
                  </span>{' '}
                  ligne(s) avec avertissement.
                </>
              )}
            </p>
            {result.errors.length > 0 && (
              <ul className="max-h-48 space-y-1 overflow-y-auto rounded border border-border p-2 text-xs">
                {result.errors.map((e, i) => (
                  <li key={i}>
                    <span className="font-mono text-muted-foreground">
                      L{e.row}
                    </span>{' '}
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
