import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Trash2, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { UserAvatar } from '@/components/UserAvatar';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { RichTextEditor, RichTextView } from '@/features/issues/RichTextEditor';
import { LabelPicker } from '@/features/issues/LabelPicker';
import { CommentsSection } from '@/features/comments/CommentsSection';
import { AttachmentsSection } from '@/features/attachments/AttachmentsSection';
import { ActivitySection } from '@/features/activity/ActivitySection';
import { ImportCsvDialog } from '@/features/issues/ImportCsvDialog';
import {
  addDependency,
  deleteIssue,
  fetchIssues,
  fetchIssue,
  removeDependency,
  updateIssue,
} from '@/features/issues/api';
import type { UpdateIssuePayload } from '@/features/issues/types';
import { useProject } from '@/features/projects/useProject';
import {
  ISSUE_STATUSES,
  PRIORITIES,
  PRIORITY_META,
  STATUS_META,
  STORY_POINT_SCALE,
  type IssueStatus,
  type Priority,
} from '@/lib/issues';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

const NONE = '__none__';

export default function IssueDetailPage() {
  const { project } = useProject();
  const { issueKey } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const canEdit = project.my_role === 'admin' || project.my_role === 'member';

  const query = useQuery({
    queryKey: queryKeys.issues.detail(issueKey!),
    queryFn: () => fetchIssue(issueKey!),
    enabled: !!issueKey,
  });

  // Epics du projet (pour rattacher un enfant).
  const epicsQuery = useQuery({
    queryKey: queryKeys.issues.list(project.id, { type: 'epic' }),
    queryFn: () => fetchIssues(project.id, { type: 'epic' }),
  });

  const mutation = useMutation({
    mutationFn: (payload: UpdateIssuePayload) => updateIssue(issueKey!, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.issues.detail(issueKey!), updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.activity.list(issueKey!),
      });
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const patch = (payload: UpdateIssuePayload) => mutation.mutate(payload);

  const removeMutation = useMutation({
    mutationFn: () => deleteIssue(issueKey!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
      toast.success('Ticket supprimé');
      navigate(`/projects/${project.id}/issues`);
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const invalidateDeps = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.issues.detail(issueKey!) });
    queryClient.invalidateQueries({ queryKey: queryKeys.timeline.view(project.id) });
    void query.refetch();
  };
  const addDepMutation = useMutation({
    mutationFn: (targetKey: string) =>
      addDependency(issueKey!, { target_key: targetKey }),
    onSuccess: () => {
      invalidateDeps();
      toast.success('Dépendance ajoutée');
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });
  const removeDepMutation = useMutation({
    mutationFn: (depId: number) => removeDependency(issueKey!, depId),
    onSuccess: () => invalidateDeps(),
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  const [summary, setSummary] = useState('');
  const [description, setDescription] = useState('');
  const [descDirty, setDescDirty] = useState(false);
  const [depTarget, setDepTarget] = useState('');
  const [importOpen, setImportOpen] = useState(false);

  const issue = query.data;

  useEffect(() => {
    if (issue) {
      setSummary(issue.summary);
      setDescription(issue.description ?? '');
      setDescDirty(false);
    }
  }, [issue]);

  if (query.isLoading) {
    return (
      <div className="p-6">
        <ListSkeleton />
      </div>
    );
  }
  if (query.isError || !issue) {
    return (
      <div className="p-6">
        <ErrorState
          title="Ticket introuvable"
          onRetry={() => query.refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <IssueTypeBadge type={issue.type} />
        <span className="font-mono">{issue.key}</span>
        {canEdit && (
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto text-destructive"
            onClick={() => removeMutation.mutate()}
            disabled={removeMutation.isPending}
          >
            <Trash2 className="h-4 w-4" />
            Supprimer
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_18rem]">
        {/* ---- Colonne principale ---- */}
        <div className="space-y-6">
          <Input
            value={summary}
            disabled={!canEdit}
            onChange={(e) => setSummary(e.target.value)}
            onBlur={() => {
              if (summary.trim() && summary !== issue.summary) {
                patch({ summary: summary.trim() });
              }
            }}
            className="h-auto border-transparent px-0 text-xl font-bold shadow-none focus-visible:border-input focus-visible:px-3"
          />

          <section>
            <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
              Description
            </h2>
            {canEdit ? (
              <div className="space-y-2">
                <RichTextEditor
                  content={issue.description ?? ''}
                  onChange={(html) => {
                    setDescription(html);
                    setDescDirty(true);
                  }}
                />
                {descDirty && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        patch({ description });
                        setDescDirty(false);
                      }}
                    >
                      Enregistrer
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setDescription(issue.description ?? '');
                        setDescDirty(false);
                      }}
                    >
                      Annuler
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <RichTextView html={issue.description} />
            )}
          </section>

          <section>
            <h2 className="mb-2 text-sm font-semibold text-muted-foreground">
              Dépendances
            </h2>
            <ul className="space-y-1">
              {(issue.dependencies ?? []).map((dep) => (
                <li
                  key={dep.id}
                  className="flex items-center gap-2 text-sm"
                >
                  <span className="text-xs font-medium text-muted-foreground">
                    {dep.direction === 'outward' ? 'bloque' : 'bloqué par'}
                  </span>
                  <Link
                    to={`/projects/${project.id}/issues/${dep.issue.key}`}
                    className="font-mono text-xs hover:text-primary hover:underline"
                  >
                    {dep.issue.key}
                  </Link>
                  <span className="truncate">{dep.issue.summary}</span>
                  {canEdit && (
                    <button
                      type="button"
                      aria-label="Retirer la dépendance"
                      className="ml-auto text-muted-foreground hover:text-destructive"
                      onClick={() => removeDepMutation.mutate(dep.id)}
                    >
                      ✕
                    </button>
                  )}
                </li>
              ))}
              {(issue.dependencies ?? []).length === 0 && (
                <li className="text-sm text-muted-foreground">Aucune.</li>
              )}
            </ul>
            {canEdit && (
              <form
                className="mt-2 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const t = depTarget.trim().toUpperCase();
                  if (t) addDepMutation.mutate(t);
                  setDepTarget('');
                }}
              >
                <Input
                  placeholder="Ce ticket bloque… (ex. JIR-4)"
                  value={depTarget}
                  onChange={(e) => setDepTarget(e.target.value)}
                  className="max-w-xs font-mono"
                />
                <Button type="submit" size="sm" disabled={addDepMutation.isPending}>
                  Ajouter
                </Button>
              </form>
            )}
          </section>

          {issue.type === 'epic' && (
            <section>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                Tickets enfants
                {issue.progress && (
                  <span className="font-normal">
                    ({issue.progress.done}/{issue.progress.total})
                  </span>
                )}
                {canEdit && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-auto"
                    onClick={() => setImportOpen(true)}
                  >
                    <Upload className="h-4 w-4" />
                    Importer CSV
                  </Button>
                )}
              </h2>
              {issue.children.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun enfant.</p>
              ) : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {issue.children.map((child) => (
                    <li key={child.id}>
                      <Link
                        to={`/projects/${project.id}/issues/${child.key}`}
                        className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-surface"
                      >
                        <IssueTypeBadge type={child.type} showLabel={false} />
                        <span className="font-mono text-xs text-muted-foreground">
                          {child.key}
                        </span>
                        <span className="flex-1 truncate">{child.summary}</span>
                        <StatusBadge status={child.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <AttachmentsSection issueKey={issue.key} canEdit={canEdit} />
          <CommentsSection issueKey={issue.key} canComment={canEdit} />
          <ActivitySection issueKey={issue.key} />

          {issue.type === 'epic' && (
            <ImportCsvDialog
              projectId={project.id}
              defaultEpicId={issue.id}
              open={importOpen}
              onOpenChange={setImportOpen}
            />
          )}
        </div>

        {/* ---- Sidebar métadonnées ---- */}
        <aside className="space-y-4 rounded-lg border border-border p-4">
          <Field label="Statut">
            <Select
              value={issue.status}
              disabled={!canEdit}
              onValueChange={(v) => patch({ status: v as IssueStatus })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ISSUE_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_META[s].label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Assigné">
            <Select
              value={issue.assignee_id ? String(issue.assignee_id) : NONE}
              disabled={!canEdit}
              onValueChange={(v) =>
                patch({ assignee_id: v === NONE ? null : v })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Non assigné</SelectItem>
                {project.members.map((m) => (
                  <SelectItem key={m.user_id} value={String(m.user_id)}>
                    {m.user.full_name || m.user.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Priorité">
            <Select
              value={issue.priority}
              disabled={!canEdit}
              onValueChange={(v) => patch({ priority: v as Priority })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRIORITIES.map((p) => (
                  <SelectItem key={p} value={p}>
                    {PRIORITY_META[p].label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field label="Story points">
            <Select
              value={issue.story_points != null ? String(issue.story_points) : NONE}
              disabled={!canEdit}
              onValueChange={(v) =>
                patch({ story_points: v === NONE ? null : Number(v) })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>—</SelectItem>
                {STORY_POINT_SCALE.map((p) => (
                  <SelectItem key={p} value={String(p)}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          {issue.type !== 'epic' && (
            <Field label="Epic parent">
              <Select
                value={issue.epic_id ? String(issue.epic_id) : NONE}
                disabled={!canEdit}
                onValueChange={(v) => patch({ epic_id: v === NONE ? null : v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Aucun" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Aucun</SelectItem>
                  {(epicsQuery.data ?? [])
                    .filter((e) => e.id !== issue.id)
                    .map((e) => (
                      <SelectItem key={e.id} value={String(e.id)}>
                        {e.key} · {e.summary}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          <Field label="Labels">
            <LabelPicker
              projectId={project.id}
              selectedIds={issue.labels.map((l) => l.id)}
              onChange={(ids) => patch({ label_ids: ids })}
              disabled={!canEdit}
            />
          </Field>

          <Field label="Échéance">
            <Input
              type="date"
              disabled={!canEdit}
              value={issue.due_date ?? ''}
              onChange={(e) => patch({ due_date: e.target.value || null })}
            />
          </Field>

          <div className="border-t border-border pt-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span>Rapporteur :</span>
              <UserAvatar
                name={issue.reporter.full_name || issue.reporter.email}
                src={issue.reporter.avatar_url}
                size="sm"
              />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}
