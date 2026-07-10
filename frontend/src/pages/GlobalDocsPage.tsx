import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EmptyState } from '@/components/EmptyState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { MarkdownView } from '@/features/documents/MarkdownView';
import {
  createDocument,
  createGeneralDocument,
  deleteDocument,
  fetchAllDocuments,
  fetchDocument,
  updateDocument,
  type GlobalDocumentSummary,
} from '@/features/documents/api';
import { fetchProjects } from '@/features/projects/api';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const GENERAL = 'general';
type Mode = 'view' | 'edit';

export default function GlobalDocsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>('view');
  const [draft, setDraft] = useState({ title: '', content: '' });
  const [scope, setScope] = useState<string>(GENERAL);
  const creating = mode === 'edit' && selectedId === null;

  const listQuery = useQuery({
    queryKey: queryKeys.documents.all,
    queryFn: fetchAllDocuments,
  });
  const projectsQuery = useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => fetchProjects(false),
  });

  const docQuery = useQuery({
    queryKey: queryKeys.documents.detail(selectedId ?? -1),
    queryFn: () => fetchDocument(selectedId!),
    enabled: selectedId !== null && mode === 'view',
  });

  const groups = useMemo(() => {
    const map = new Map<string, { label: string; docs: GlobalDocumentSummary[] }>();
    for (const d of listQuery.data ?? []) {
      const key = d.project ? String(d.project.id) : GENERAL;
      const label = d.project ? d.project.name : 'Général';
      if (!map.has(key)) map.set(key, { label, docs: [] });
      map.get(key)!.docs.push(d);
    }
    // Général en premier.
    return [...map.entries()].sort((a, b) =>
      a[0] === GENERAL ? -1 : b[0] === GENERAL ? 1 : a[1].label.localeCompare(b[1].label)
    );
  }, [listQuery.data]);

  useEffect(() => {
    if (selectedId === null && mode === 'view' && listQuery.data?.length) {
      setSelectedId(listQuery.data[0].id);
    }
  }, [listQuery.data, selectedId, mode]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.documents.all });
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!creating) return updateDocument(selectedId!, draft);
      return scope === GENERAL
        ? createGeneralDocument(draft)
        : createDocument(scope, draft);
    },
    onSuccess: (doc) => {
      invalidate();
      queryClient.invalidateQueries({
        queryKey: queryKeys.documents.detail(doc.id),
      });
      setSelectedId(doc.id);
      setMode('view');
      toast.success('Document enregistré');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteDocument(id),
    onSuccess: () => {
      invalidate();
      setSelectedId(null);
      setMode('view');
      toast.success('Document supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function startCreate() {
    setSelectedId(null);
    setScope(GENERAL);
    setDraft({ title: '', content: '# Nouveau document\n\n' });
    setMode('edit');
  }

  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="shrink-0 border-b border-border md:w-64 md:overflow-y-auto md:border-b-0 md:border-r">
        <div className="flex items-center justify-between p-3">
          <h2 className="text-sm font-semibold">Documentation</h2>
          <Button size="sm" variant="ghost" onClick={startCreate}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {listQuery.isLoading ? (
          <div className="p-3">
            <ListSkeleton rows={4} />
          </div>
        ) : (
          <div className="max-h-64 overflow-y-auto md:max-h-none">
            {groups.map(([key, group]) => (
              <div key={key} className="mb-2">
                <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.label}
                </p>
                <ul>
                  {group.docs.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedId(d.id);
                          setMode('view');
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-surface',
                          selectedId === d.id &&
                            mode === 'view' &&
                            'bg-surface font-medium text-primary'
                        )}
                      >
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{d.title}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </aside>

      <div className="min-w-0 flex-1 overflow-auto p-6">
        {mode === 'edit' ? (
          <div className="space-y-3">
            {creating && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Emplacement :</span>
                <Select value={scope} onValueChange={setScope}>
                  <SelectTrigger className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={GENERAL}>Général (hors projet)</SelectItem>
                    {(projectsQuery.data ?? []).map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <Input
              placeholder="Titre du document"
              value={draft.title}
              onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
            />
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <Textarea
                placeholder="Contenu en Markdown…"
                value={draft.content}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, content: e.target.value }))
                }
                className="min-h-[24rem] font-mono text-sm"
              />
              <div className="min-h-[24rem] overflow-auto rounded-md border border-border p-4">
                <MarkdownView content={draft.content} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => saveMutation.mutate()}
                disabled={!draft.title.trim() || saveMutation.isPending}
              >
                Enregistrer
              </Button>
              <Button variant="ghost" onClick={() => setMode('view')}>
                Annuler
              </Button>
            </div>
          </div>
        ) : listQuery.data && listQuery.data.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Aucun document"
            description="Créez de la documentation générale ou liée à un projet."
            actionLabel="Nouveau document"
            onAction={startCreate}
          />
        ) : docQuery.data ? (
          <article className="space-y-4">
            <header className="flex items-start justify-between gap-2">
              <h1 className="text-2xl font-bold">{docQuery.data.title}</h1>
              <div className="flex shrink-0 gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setDraft({
                      title: docQuery.data!.title,
                      content: docQuery.data!.content,
                    });
                    setMode('edit');
                  }}
                >
                  Éditer
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive"
                  onClick={() => deleteMutation.mutate(docQuery.data!.id)}
                >
                  Supprimer
                </Button>
              </div>
            </header>
            <MarkdownView content={docQuery.data.content} />
          </article>
        ) : null}
      </div>
    </div>
  );
}
