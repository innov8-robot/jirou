import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { EmptyState } from '@/components/EmptyState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { MarkdownView } from '@/features/documents/MarkdownView';
import {
  createDocument,
  deleteDocument,
  fetchDocument,
  fetchDocuments,
  updateDocument,
} from '@/features/documents/api';
import { useProject } from '@/features/projects/useProject';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

type Mode = 'view' | 'edit';

export default function DocumentsPage() {
  const { project } = useProject();
  const canEdit = project.my_role === 'admin' || project.my_role === 'member';
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>('view');
  const [draft, setDraft] = useState({ title: '', content: '' });
  const creating = mode === 'edit' && selectedId === null;

  const listQuery = useQuery({
    queryKey: queryKeys.documents.list(project.id),
    queryFn: () => fetchDocuments(project.id),
  });

  // Sélection initiale.
  useEffect(() => {
    if (selectedId === null && mode === 'view' && listQuery.data?.length) {
      setSelectedId(Number(listQuery.data[0].id));
    }
  }, [listQuery.data, selectedId, mode]);

  const docQuery = useQuery({
    queryKey: queryKeys.documents.detail(selectedId ?? -1),
    queryFn: () => fetchDocument(selectedId!),
    enabled: selectedId !== null && mode === 'view',
  });

  const invalidateList = () =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.documents.list(project.id),
    });

  const saveMutation = useMutation({
    mutationFn: () =>
      creating
        ? createDocument(project.id, draft)
        : updateDocument(selectedId!, draft),
    onSuccess: (doc) => {
      invalidateList();
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
      invalidateList();
      setSelectedId(null);
      setMode('view');
      toast.success('Document supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  function startCreate() {
    setSelectedId(null);
    setDraft({ title: '', content: '# Nouveau document\n\n' });
    setMode('edit');
  }

  function startEdit() {
    if (docQuery.data) {
      setDraft({
        title: docQuery.data.title,
        content: docQuery.data.content,
      });
      setMode('edit');
    }
  }

  const docs = listQuery.data ?? [];

  return (
    <div className="flex flex-col md:h-full md:flex-row">
      {/* Liste des documents */}
      <aside className="shrink-0 border-b border-border md:w-60 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between p-3">
          <h2 className="text-sm font-semibold">Documents</h2>
          {canEdit && (
            <Button size="sm" variant="ghost" onClick={startCreate}>
              <Plus className="h-4 w-4" />
            </Button>
          )}
        </div>
        {listQuery.isLoading ? (
          <div className="p-3">
            <ListSkeleton rows={3} />
          </div>
        ) : (
          <ul className="max-h-48 overflow-y-auto md:max-h-none">
            {docs.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(Number(d.id));
                    setMode('view');
                  }}
                  className={cn(
                    'flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface',
                    selectedId === Number(d.id) &&
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
        )}
      </aside>

      {/* Contenu */}
      <div className="min-w-0 flex-1 overflow-auto p-6">
        {mode === 'edit' ? (
          <div className="space-y-3">
            <Input
              placeholder="Titre du document"
              value={draft.title}
              onChange={(e) =>
                setDraft((d) => ({ ...d, title: e.target.value }))
              }
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
              <Button
                variant="ghost"
                onClick={() => {
                  setMode('view');
                  if (creating) setSelectedId(docs.length ? Number(docs[0].id) : null);
                }}
              >
                Annuler
              </Button>
            </div>
          </div>
        ) : docs.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Aucun document"
            description="Créez de la documentation en Markdown pour ce projet."
            actionLabel={canEdit ? 'Nouveau document' : undefined}
            onAction={canEdit ? startCreate : undefined}
          />
        ) : docQuery.data ? (
          <article className="space-y-4">
            <header className="flex items-start justify-between gap-2">
              <h1 className="text-2xl font-bold">{docQuery.data.title}</h1>
              {canEdit && (
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="outline" onClick={startEdit}>
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
              )}
            </header>
            <MarkdownView content={docQuery.data.content} />
          </article>
        ) : null}
      </div>
    </div>
  );
}
