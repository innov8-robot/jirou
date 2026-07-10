import { NavLink, Outlet, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { UserAvatar } from '@/components/UserAvatar';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { cn } from '@/lib/utils';
import { queryKeys } from '@/lib/queryKeys';
import { fetchProject } from './api';
import { ProjectKeyBadge } from './ProjectKeyBadge';
import type { ProjectContext } from './useProject';

interface Tab {
  label: string;
  to: string;
  end?: boolean;
  placeholder?: boolean;
}

const TABS: Tab[] = [
  { label: 'Résumé', to: '.', end: true },
  { label: 'Tickets', to: 'issues' },
  { label: 'Board', to: 'board' },
  { label: 'Backlog', to: 'backlog' },
  { label: 'Timeline', to: 'timeline' },
  { label: 'Paramètres', to: 'settings' },
];

export function ProjectLayout() {
  const { projectId } = useParams();
  const query = useQuery({
    queryKey: queryKeys.projects.detail(projectId!),
    queryFn: () => fetchProject(projectId!),
    enabled: !!projectId,
  });

  if (query.isLoading) {
    return (
      <div className="p-6">
        <ListSkeleton />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="p-6">
        <ErrorState
          title="Projet introuvable"
          description="Ce projet n'existe pas ou vous n'y avez pas accès."
          onRetry={() => query.refetch()}
        />
      </div>
    );
  }

  const project = query.data;

  return (
    <div className="flex flex-col">
      <header className="border-b border-border px-6 pt-6">
        <div className="flex items-center gap-3">
          <ProjectKeyBadge projectKey={project.key} color={project.color} />
          <div>
            <h1 className="text-xl font-bold">{project.name}</h1>
            <p className="font-mono text-xs text-muted-foreground">
              {project.key}
            </p>
          </div>
          <div className="ml-auto flex -space-x-2">
            {project.members.slice(0, 5).map((m) => (
              <UserAvatar
                key={m.user_id}
                name={m.user.full_name || m.user.email}
                src={m.user.avatar_url}
                size="sm"
                className="ring-2 ring-background"
              />
            ))}
          </div>
        </div>

        <nav className="mt-4 flex gap-1 overflow-x-auto">
          {TABS.map((tab) =>
            tab.placeholder ? (
              <span
                key={tab.to}
                className="cursor-default whitespace-nowrap px-3 py-2 text-sm text-muted-foreground/50"
                title="Bientôt disponible"
              >
                {tab.label}
              </span>
            ) : (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  cn(
                    'whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'border-primary text-foreground'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )
                }
              >
                {tab.label}
              </NavLink>
            )
          )}
        </nav>
      </header>

      <div className="flex-1">
        <Outlet context={{ project } satisfies ProjectContext} />
      </div>
    </div>
  );
}
