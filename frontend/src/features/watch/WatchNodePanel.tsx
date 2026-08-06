import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Upload, X } from 'lucide-react';

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
import { UserAvatar } from '@/components/UserAvatar';
import { MarkdownView } from '@/features/documents/MarkdownView';
import { WatchMediaGallery } from './WatchMediaGallery';
import { WatchCsvImportDialog } from './WatchCsvImportDialog';
import {
  WATCH_STATUSES,
  WATCH_STATUS_META,
  WATCH_TYPES,
  WATCH_TYPE_META,
  createWatchComment,
  deleteNode,
  deleteWatchComment,
  fetchNode,
  fetchNodes,
  fetchWatchComments,
  updateNode,
  type WatchNodeType,
  type WatchStatus,
} from './api';
import { parentOptions } from './graph';
import { useAuth } from '@/features/auth/useAuth';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NO_STATUS = '__none__';
const NO_PARENT = '__root__';

export function WatchNodePanel({
  nodeId,
  onClose,
  onDeleted,
  onAddChild,
}: {
  nodeId: number;
  onClose: () => void;
  onDeleted: () => void;
  onAddChild: (parentId: number) => void;
}) {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const nodeQuery = useQuery({
    queryKey: queryKeys.watch.node(nodeId),
    queryFn: () => fetchNode(nodeId),
  });
  const commentsQuery = useQuery({
    queryKey: queryKeys.watch.comments(nodeId),
    queryFn: () => fetchWatchComments(nodeId),
  });
  // Même clé que le graphe : la liste est déjà en cache, aucun appel de plus.
  const { data: allNodes = [] } = useQuery({
    queryKey: queryKeys.watch.nodes,
    queryFn: fetchNodes,
  });
  const parents = parentOptions(allNodes, nodeId);

  const [title, setTitle] = useState('');
  const [editingNote, setEditingNote] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [comment, setComment] = useState('');
  const [importOpen, setImportOpen] = useState(false);

  const node = nodeQuery.data;
  useEffect(() => {
    if (node) {
      setTitle(node.title);
      setNoteDraft(node.note);
      setEditingNote(false);
    }
  }, [node]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.watch.node(nodeId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
  };

  const patchMut = useMutation({
    mutationFn: (payload: Parameters<typeof updateNode>[1]) =>
      updateNode(nodeId, payload),
    onSuccess: refresh,
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const delMut = useMutation({
    mutationFn: () => deleteNode(nodeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
      toast.success('Nœud supprimé');
      onDeleted();
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const addCommentMut = useMutation({
    mutationFn: () => createWatchComment(nodeId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.comments(nodeId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.nodes });
      setComment('');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const delCommentMut = useMutation({
    mutationFn: (id: number) => deleteWatchComment(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.watch.comments(nodeId) }),
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <aside className="flex h-full w-full flex-col overflow-y-auto border-l border-border bg-background md:w-[26rem]">
      <header className="flex items-center gap-2 border-b border-border p-3">
        <span className="text-sm font-semibold text-muted-foreground">Nœud</span>
        <div className="ml-auto flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onAddChild(nodeId)}
            title="Ajouter un sous-nœud"
          >
            <Plus className="h-4 w-4" />
            Sous-nœud
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setImportOpen(true)}
            title="Importer des sous-nœuds depuis un CSV"
          >
            <Upload className="h-4 w-4" />
            CSV
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Fermer">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {!node ? (
        <div className="p-4 text-sm text-muted-foreground">Chargement…</div>
      ) : (
        <div className="space-y-5 p-4">
          {/* Titre */}
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => title.trim() && title !== node.title && patchMut.mutate({ title: title.trim() })}
            className="text-lg font-semibold"
          />

          {/* Type */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Type</p>
            <Select
              value={node.type}
              onValueChange={(v) => patchMut.mutate({ type: v as WatchNodeType })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WATCH_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {WATCH_TYPE_META[t].label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Parent */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Rattaché à
            </p>
            <Select
              value={node.parent_id == null ? NO_PARENT : String(node.parent_id)}
              onValueChange={(v) =>
                patchMut.mutate({
                  parent_id: v === NO_PARENT ? null : Number(v),
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_PARENT}>
                  Aucun — thème racine
                </SelectItem>
                {parents.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Le nœud emporte ses sous-nœuds. Sa descendance n'est pas proposée,
              cela formerait une boucle.
            </p>
          </div>

          {/* Statut */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Statut</p>
            <Select
              value={node.status ?? NO_STATUS}
              onValueChange={(v) =>
                patchMut.mutate({ status: v === NO_STATUS ? null : (v as WatchStatus) })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_STATUS}>—</SelectItem>
                {WATCH_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {WATCH_STATUS_META[s].label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Note */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase text-muted-foreground">Note</p>
              {!editingNote && (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => {
                    setNoteDraft(node.note);
                    setEditingNote(true);
                  }}
                >
                  Éditer
                </button>
              )}
            </div>
            {editingNote ? (
              <div className="space-y-2">
                <Textarea
                  value={noteDraft}
                  onChange={(e) => setNoteDraft(e.target.value)}
                  rows={8}
                  className="font-mono text-sm"
                  placeholder="Note en Markdown…"
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      patchMut.mutate(
                        { note: noteDraft },
                        { onSuccess: () => setEditingNote(false) }
                      )
                    }
                  >
                    Enregistrer
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditingNote(false)}>
                    Annuler
                  </Button>
                </div>
              </div>
            ) : (
              <MarkdownView content={node.note} />
            )}
          </div>

          {/* Médias */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Médias</p>
            <WatchMediaGallery nodeId={nodeId} media={node.media} />
          </div>

          {/* Commentaires */}
          <div className="space-y-2">
            <p className="text-xs font-medium uppercase text-muted-foreground">
              Commentaires
            </p>
            <ul className="space-y-2">
              {(commentsQuery.data ?? []).map((c) => (
                <li key={c.id} className="flex items-start gap-2 text-sm">
                  <UserAvatar
                    name={c.author?.full_name || '?'}
                    src={c.author?.avatar_url}
                    size="sm"
                  />
                  <div className="flex-1">
                    <p className="whitespace-pre-wrap">{c.body}</p>
                  </div>
                  {(c.author?.id === user?.id || user?.role === 'admin') && (
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-destructive"
                      onClick={() => delCommentMut.mutate(c.id)}
                      aria-label="Supprimer"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <form
              className="flex gap-2"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                if (comment.trim()) addCommentMut.mutate();
              }}
            >
              <Input
                placeholder="Ajouter un commentaire…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <Button type="submit" size="sm" disabled={addCommentMut.isPending}>
                Envoyer
              </Button>
            </form>
          </div>

          {/* Suppression */}
          <div className="border-t border-border pt-3">
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              onClick={() => {
                if (confirm('Supprimer ce nœud et tous ses sous-nœuds ?'))
                  delMut.mutate();
              }}
            >
              Supprimer le nœud
            </Button>
          </div>
        </div>
      )}

      {node && (
        <WatchCsvImportDialog
          nodeId={nodeId}
          nodeTitle={node.title}
          open={importOpen}
          onOpenChange={setImportOpen}
        />
      )}
    </aside>
  );
}
