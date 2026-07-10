import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { IssueTypeBadge } from '@/components/IssueTypeBadge';
import { StatusBadge } from '@/components/StatusBadge';
import { UserAvatar } from '@/components/UserAvatar';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { fetchProjectStats } from '@/features/stats/api';
import { useProject } from '@/features/projects/useProject';
import {
  ISSUE_STATUSES,
  ISSUE_TYPES,
  ISSUE_TYPE_META,
  STATUS_META,
} from '@/lib/issues';
import { queryKeys } from '@/lib/queryKeys';

export default function ProjectOverviewPage() {
  const { project } = useProject();
  const query = useQuery({
    queryKey: queryKeys.stats.project(project.id),
    queryFn: () => fetchProjectStats(project.id),
  });

  if (query.isLoading)
    return (
      <div className="p-6">
        <ListSkeleton />
      </div>
    );
  if (query.isError || !query.data)
    return (
      <div className="p-6">
        <ErrorState
          description="Impossible de charger le tableau de bord."
          onRetry={() => query.refetch()}
        />
      </div>
    );

  const stats = query.data;
  const maxStatus = Math.max(1, ...Object.values(stats.by_status));
  const as = stats.active_sprint;

  return (
    <div className="space-y-6 p-6">
      {project.description && (
        <p className="text-sm text-muted-foreground">{project.description}</p>
      )}

      {/* Tuiles */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Tickets" value={stats.total} />
        {ISSUE_STATUSES.map((s) => (
          <Tile
            key={s}
            label={STATUS_META[s].label}
            value={stats.by_status[s]}
            color={STATUS_META[s].color}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Répartition par statut */}
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-3 text-sm font-semibold">Par statut</h2>
          <div className="space-y-2">
            {ISSUE_STATUSES.map((s) => (
              <BarRow
                key={s}
                label={STATUS_META[s].label}
                value={stats.by_status[s]}
                max={maxStatus}
                color={STATUS_META[s].color}
              />
            ))}
          </div>
        </section>

        {/* Répartition par type */}
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-3 text-sm font-semibold">Par type</h2>
          <div className="space-y-2">
            {ISSUE_TYPES.map((t) => (
              <BarRow
                key={t}
                label={ISSUE_TYPE_META[t].label}
                value={stats.by_type[t]}
                max={Math.max(1, ...Object.values(stats.by_type))}
                color={ISSUE_TYPE_META[t].color}
              />
            ))}
          </div>
        </section>

        {/* Sprint actif */}
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-3 text-sm font-semibold">Sprint actif</h2>
          {as ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{as.sprint.name}</span>
                <span className="text-muted-foreground">
                  {as.done}/{as.total} tickets · {as.points_done}/
                  {as.points_total} pts
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{
                    width: `${as.total ? Math.round((as.done / as.total) * 100) : 0}%`,
                  }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucun sprint actif.{' '}
              <Link
                to={`/projects/${project.id}/backlog`}
                className="text-primary hover:underline"
              >
                Aller au backlog
              </Link>
            </p>
          )}
        </section>

        {/* Par assigné */}
        <section className="rounded-lg border border-border p-4">
          <h2 className="mb-3 text-sm font-semibold">Par assigné</h2>
          <ul className="space-y-2">
            {stats.by_assignee.map((row, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                {row.user ? (
                  <>
                    <UserAvatar
                      name={row.user.full_name || row.user.email}
                      src={row.user.avatar_url}
                      size="sm"
                    />
                    <span className="flex-1 truncate">
                      {row.user.full_name || row.user.email}
                    </span>
                  </>
                ) : (
                  <span className="flex-1 text-muted-foreground">Non assigné</span>
                )}
                <span className="text-muted-foreground">{row.count}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* Récents */}
      <section className="rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold">Récemment mis à jour</h2>
        <ul className="divide-y divide-border">
          {stats.recent.map((issue) => (
            <li key={issue.id}>
              <Link
                to={`/projects/${project.id}/issues/${issue.key}`}
                className="flex items-center gap-2 py-2 text-sm hover:text-primary"
              >
                <IssueTypeBadge type={issue.type} showLabel={false} />
                <span className="font-mono text-xs text-muted-foreground">
                  {issue.key}
                </span>
                <span className="flex-1 truncate">{issue.summary}</span>
                <StatusBadge status={issue.status} />
              </Link>
            </li>
          ))}
          {stats.recent.length === 0 && (
            <li className="py-2 text-sm text-muted-foreground">Aucun ticket.</li>
          )}
        </ul>
      </section>
    </div>
  );
}

function Tile({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-2xl font-bold" style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function BarRow({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 shrink-0 text-muted-foreground">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round((value / max) * 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
      <span className="w-6 shrink-0 text-right text-muted-foreground">
        {value}
      </span>
    </div>
  );
}
