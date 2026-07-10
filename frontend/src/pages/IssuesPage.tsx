import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityIcon } from '@/components/PriorityIcon';
import { StoryPoints } from '@/components/StoryPoints';
import { UserAvatar } from '@/components/UserAvatar';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { LabelBadge } from '@/features/issues/LabelBadge';
import { SavedViewsControl } from '@/features/views/SavedViewsControl';
import { fetchIssues } from '@/features/issues/api';
import type { IssueFilters } from '@/features/issues/types';
import { useProject } from '@/features/projects/useProject';
import { ISSUE_STATUSES, ISSUE_TYPES } from '@/lib/issues';
import { STATUS_META, ISSUE_TYPE_META } from '@/lib/issues';
import { queryKeys } from '@/lib/queryKeys';
import { useUiStore } from '@/stores/uiStore';

const ALL = 'all';

export default function IssuesPage() {
  const { project } = useProject();
  const openCreateIssue = useUiStore((s) => s.openCreateIssue);

  const [search, setSearch] = useState('');
  const [type, setType] = useState<string>(ALL);
  const [status, setStatus] = useState<string>(ALL);
  const [assignee, setAssignee] = useState<string>(ALL);

  const filters: IssueFilters = {
    search: search.trim() || undefined,
    type: type === ALL ? undefined : (type as IssueFilters['type']),
    status: status === ALL ? undefined : (status as IssueFilters['status']),
    assignee_id: assignee === ALL ? undefined : assignee,
  };

  const query = useQuery({
    queryKey: queryKeys.issues.list(project.id, filters as Record<string, unknown>),
    queryFn: () => fetchIssues(project.id, filters),
  });

  function reset() {
    setSearch('');
    setType(ALL);
    setStatus(ALL);
    setAssignee(ALL);
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Rechercher…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={type} onValueChange={setType}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous types</SelectItem>
            {ISSUE_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {ISSUE_TYPE_META[t].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Statut" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous statuts</SelectItem>
            {ISSUE_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_META[s].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={assignee} onValueChange={setAssignee}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Assigné" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Tous assignés</SelectItem>
            {project.members.map((m) => (
              <SelectItem key={m.user_id} value={String(m.user_id)}>
                {m.user.full_name || m.user.email}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="ghost" size="sm" onClick={reset}>
          Réinitialiser
        </Button>
        <div className="ml-auto">
          <SavedViewsControl
            projectId={project.id}
            currentFilters={{ search, type, status, assignee }}
            onApply={(f) => {
              setSearch((f.search as string) ?? '');
              setType((f.type as string) ?? ALL);
              setStatus((f.status as string) ?? ALL);
              setAssignee((f.assignee as string) ?? ALL);
            }}
          />
        </div>
      </div>

      {query.isLoading && <ListSkeleton />}
      {query.isError && (
        <ErrorState
          description="Impossible de charger les tickets."
          onRetry={() => query.refetch()}
        />
      )}

      {query.data && query.data.length === 0 && (
        <EmptyState
          title="Aucun ticket"
          description="Créez votre premier ticket pour ce projet."
          actionLabel="Créer un ticket"
          onAction={openCreateIssue}
        />
      )}

      {query.data && query.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Clé</th>
                <th className="px-3 py-2 font-medium">Résumé</th>
                <th className="px-3 py-2 font-medium">Statut</th>
                <th className="px-3 py-2 font-medium">Prio</th>
                <th className="px-3 py-2 font-medium">Points</th>
                <th className="px-3 py-2 font-medium">Assigné</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((issue) => (
                <tr
                  key={issue.id}
                  className="border-b border-border last:border-0 hover:bg-surface"
                >
                  <td className="px-3 py-2">
                    <IssueTypeBadge type={issue.type} showLabel={false} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted-foreground">
                    {issue.key}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      to={`/projects/${project.id}/issues/${issue.key}`}
                      className="font-medium hover:text-primary hover:underline"
                    >
                      {issue.summary}
                    </Link>
                    {issue.labels.length > 0 && (
                      <span className="ml-2 inline-flex gap-1 align-middle">
                        {issue.labels.map((l) => (
                          <LabelBadge key={l.id} label={l} />
                        ))}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={issue.status} />
                  </td>
                  <td className="px-3 py-2">
                    <PriorityIcon priority={issue.priority} />
                  </td>
                  <td className="px-3 py-2">
                    {issue.story_points != null && (
                      <StoryPoints points={issue.story_points} />
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {issue.assignee ? (
                      <UserAvatar
                        name={issue.assignee.full_name || issue.assignee.email}
                        src={issue.assignee.avatar_url}
                        size="sm"
                      />
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
