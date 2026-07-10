import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AtSign, Check } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { UserAvatar } from '@/components/UserAvatar';
import { RichTextEditor, RichTextView } from '@/features/issues/RichTextEditor';
import { useProject } from '@/features/projects/useProject';
import { useAuth } from '@/features/auth/useAuth';
import {
  createComment,
  deleteComment,
  fetchComments,
  updateComment,
  type Comment,
} from './api';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.round(diff / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.round(h / 24);
  return `il y a ${d} j`;
}

export function CommentsSection({
  issueKey,
  canComment,
}: {
  issueKey: string;
  canComment: boolean;
}) {
  const { project } = useProject();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data: comments = [] } = useQuery({
    queryKey: queryKeys.comments.list(issueKey),
    queryFn: () => fetchComments(issueKey),
  });

  const [body, setBody] = useState('');
  const [editorKey, setEditorKey] = useState(0);
  const [mentions, setMentions] = useState<number[]>([]);

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: queryKeys.comments.list(issueKey),
    });

  const addMutation = useMutation({
    mutationFn: () =>
      createComment(issueKey, {
        body,
        mention_user_ids: mentions.length ? mentions : undefined,
      }),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({
        queryKey: queryKeys.activity.list(issueKey),
      });
      setBody('');
      setMentions([]);
      setEditorKey((k) => k + 1);
      toast.success('Commentaire ajouté');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const canModify = (c: Comment) =>
    c.author.id === user?.id ||
    user?.role === 'admin' ||
    project.my_role === 'admin';

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
        Commentaires
      </h2>

      <ul className="space-y-4">
        {comments.map((c) => (
          <CommentItem
            key={c.id}
            comment={c}
            canModify={canModify(c)}
            onChanged={invalidate}
          />
        ))}
        {comments.length === 0 && (
          <li className="text-sm text-muted-foreground">
            Aucun commentaire pour l'instant.
          </li>
        )}
      </ul>

      {canComment && (
        <div className="mt-4 space-y-2">
          <RichTextEditor
            key={editorKey}
            content=""
            onChange={setBody}
            placeholder="Ajouter un commentaire…"
          />
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <AtSign className="h-4 w-4" />
                  Mentionner{mentions.length ? ` (${mentions.length})` : ''}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
                <DropdownMenuLabel>Membres du projet</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {project.members.map((m) => {
                  const uid = Number(m.user_id);
                  const selected = mentions.includes(uid);
                  return (
                    <DropdownMenuItem
                      key={m.user_id}
                      onSelect={(e) => {
                        e.preventDefault();
                        setMentions((prev) =>
                          selected
                            ? prev.filter((x) => x !== uid)
                            : [...prev, uid]
                        );
                      }}
                    >
                      <span className="flex w-4 justify-center">
                        {selected && <Check className="h-3.5 w-3.5" />}
                      </span>
                      {m.user.full_name || m.user.email}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              size="sm"
              className="ml-auto"
              disabled={
                addMutation.isPending || !body.trim() || body === '<p></p>'
              }
              onClick={() => addMutation.mutate()}
            >
              Commenter
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function CommentItem({
  comment,
  canModify,
  onChanged,
}: {
  comment: Comment;
  canModify: boolean;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(comment.body);

  const updateMutation = useMutation({
    mutationFn: () => updateComment(comment.id, { body: draft }),
    onSuccess: () => {
      onChanged();
      setEditing(false);
      toast.success('Commentaire modifié');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteComment(comment.id),
    onSuccess: () => {
      onChanged();
      toast.success('Commentaire supprimé');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <li className="flex gap-3">
      <UserAvatar
        name={comment.author.full_name || comment.author.email}
        src={comment.author.avatar_url}
        size="sm"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{comment.author.full_name}</span>
          <span className="text-xs text-muted-foreground">
            {relativeTime(comment.created_at)}
          </span>
          {canModify && !editing && (
            <span className="ml-auto flex gap-2 text-xs">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setDraft(comment.body);
                  setEditing(true);
                }}
              >
                Modifier
              </button>
              <button
                type="button"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => deleteMutation.mutate()}
              >
                Supprimer
              </button>
            </span>
          )}
        </div>
        {editing ? (
          <div className="mt-1 space-y-2">
            <RichTextEditor content={comment.body} onChange={setDraft} />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => updateMutation.mutate()}>
                Enregistrer
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditing(false)}
              >
                Annuler
              </Button>
            </div>
          </div>
        ) : (
          <RichTextView html={comment.body} className="mt-1" />
        )}
      </div>
    </li>
  );
}
