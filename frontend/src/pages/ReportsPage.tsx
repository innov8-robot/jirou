import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Download, FileBarChart, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EmptyState } from '@/components/EmptyState';
import { MarkdownView } from '@/features/documents/MarkdownView';
import { generateReport, type ReportResult } from '@/features/reports/api';
import { fetchProjects } from '@/features/projects/api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const ALL = 'all';

export default function ReportsPage() {
  const [scope, setScope] = useState<string>(ALL);
  const [report, setReport] = useState<ReportResult | null>(null);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => fetchProjects(false),
  });

  const mutation = useMutation({
    mutationFn: () => generateReport(scope === ALL ? null : scope),
    onSuccess: (r) => setReport(r),
    onError: (err) => toast.error('Génération échouée', getErrorMessage(err)),
  });

  function download() {
    if (!report) return;
    const blob = new Blob([report.markdown], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jirou-rapport-${report.project_id ?? 'global'}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-6 py-6">
      <div className="flex items-center gap-2">
        <FileBarChart className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-xl font-bold">Rapports</h1>
          <p className="text-sm text-muted-foreground">
            Statistiques + synthèse automatique (admin).
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={scope} onValueChange={setScope}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous les projets (global)</SelectItem>
            {(projectsQuery.data ?? []).map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          <Sparkles className="h-4 w-4" />
          {mutation.isPending ? 'Génération…' : 'Générer le rapport'}
        </Button>
        {report && (
          <Button variant="outline" onClick={download}>
            <Download className="h-4 w-4" />
            Télécharger (.md)
          </Button>
        )}
      </div>

      {!report && !mutation.isPending && (
        <EmptyState
          icon={FileBarChart}
          title="Aucun rapport généré"
          description="Choisissez un périmètre et générez un rapport."
        />
      )}

      {report && (
        <article className="rounded-lg border border-border p-6">
          {!report.llm_used && (
            <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Synthèse IA indisponible (MISTRAL_API_KEY non configurée) — stats
              seules.
            </p>
          )}
          <MarkdownView content={report.markdown} />
        </article>
      )}
    </div>
  );
}
