import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Upload } from 'lucide-react';

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { fetchIssues, importIssuesCsv, type ImportResult } from './api';
import { CSV_HEADER, downloadCsvTemplate } from './csvTemplate';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NONE = '__none__';

interface Props {
  projectId: number | string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  /** Epic cible imposée (import de tickets enfants depuis une epic). */
  defaultEpicId?: number | string;
}

export function ImportCsvDialog({
  projectId,
  open,
  onOpenChange,
  defaultEpicId,
}: Props) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [epicId, setEpicId] = useState<string>(NONE);
  const [result, setResult] = useState<ImportResult | null>(null);

  const { data: epics = [] } = useQuery({
    queryKey: queryKeys.issues.list(projectId, { type: 'epic' }),
    queryFn: () => fetchIssues(projectId, { type: 'epic' }),
    enabled: open && defaultEpicId == null,
  });

  const mutation = useMutation({
    mutationFn: () =>
      importIssuesCsv(
        projectId,
        file!,
        defaultEpicId ?? (epicId === NONE ? null : epicId)
      ),
    onSuccess: (res) => {
      setResult(res);
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.board.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.backlog.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.view(projectId),
      });
      toast.success(`${res.created} ticket(s) importé(s)`);
    },
    onError: (err) => toast.error('Import échoué', getErrorMessage(err)),
  });

  function close(o: boolean) {
    onOpenChange(o);
    if (!o) {
      setFile(null);
      setEpicId(NONE);
      setResult(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Importer des tickets (CSV)</DialogTitle>
          <DialogDescription>
            Importez plusieurs tickets d'un coup depuis un fichier CSV.
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
                Astuce : une ligne{' '}
                <code className="rounded bg-background px-1">type=epic</code> puis
                des enfants avec{' '}
                <code className="rounded bg-background px-1">
                  epic_key=&lt;résumé de l'epic&gt;
                </code>{' '}
                crée l'epic et ses tickets d'un coup.
              </p>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadCsvTemplate()}
            >
              <Download className="h-4 w-4" />
              Télécharger un modèle
            </Button>

            <div className="space-y-1.5">
              <Label>Fichier CSV</Label>
              <input
                ref={inputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-background file:px-3 file:py-1.5 file:text-sm"
              />
            </div>

            {defaultEpicId == null && (
              <div className="space-y-1.5">
                <Label>Rattacher à une epic (optionnel)</Label>
                <Select value={epicId} onValueChange={setEpicId}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE}>Aucune</SelectItem>
                    {epics.map((e) => (
                      <SelectItem key={e.id} value={String(e.id)}>
                        {e.key} · {e.summary}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

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
                {result.created}
              </span>{' '}
              ticket(s) créé(s).
              {result.error_count > 0 && (
                <>
                  {' '}
                  <span className="font-semibold text-destructive">
                    {result.error_count}
                  </span>{' '}
                  ligne(s) avec avertissement/erreur.
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
