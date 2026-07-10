import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { LayoutGrid } from 'lucide-react';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityIcon } from '@/components/PriorityIcon';
import { EmptyState } from '@/components/EmptyState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { fetchMyIssues } from '@/features/issues/api';
import { fetchProjects } from '@/features/projects/api';
import type { Issue } from '@/features/issues/types';
import { queryKeys } from '@/lib/queryKeys';

export default function MyWorkPage() {
  const issuesQuery = useQuery({
    queryKey: queryKeys.myIssues.all,
    queryFn: fetchMyIssues,
  });
  const projectsQuery = useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => fetchProjects(false),
  });

  const projectName = new Map(
    (projectsQuery.data ?? []).map((p) => [String(p.id), p.name])
  );

  const grouped = new Map<string, Issue[]>();
  for (const issue of issuesQuery.data ?? []) {
    const k = String(issue.project_id);
    if (!grouped.has(k)) grouped.set(k, []);
    grouped.get(k)!.push(issue);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">Mon travail</h1>
        <p className="text-sm text-muted-foreground">
          Les tickets qui vous sont assignés, tous projets confondus.
        </p>
      </div>

      {issuesQuery.isLoading && <ListSkeleton />}

      {issuesQuery.data && issuesQuery.data.length === 0 && (
        <EmptyState
          icon={LayoutGrid}
          title="Rien à faire pour l'instant"
          description="Aucun ticket ne vous est assigné."
        />
      )}

      {[...grouped.entries()].map(([projectId, issues]) => (
        <section key={projectId} className="rounded-lg border border-border">
          <header className="border-b border-border px-4 py-2 font-semibold">
            {projectName.get(projectId) ?? `Projet ${projectId}`}
          </header>
          <ul className="divide-y divide-border">
            {issues.map((issue) => (
              <li key={issue.id}>
                <Link
                  to={`/projects/${issue.project_id}/issues/${issue.key}`}
                  className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-surface"
                >
                  <IssueTypeBadge type={issue.type} showLabel={false} />
                  <span className="font-mono text-xs text-muted-foreground">
                    {issue.key}
                  </span>
                  <span className="flex-1 truncate">{issue.summary}</span>
                  <PriorityIcon priority={issue.priority} />
                  <StatusBadge status={issue.status} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
