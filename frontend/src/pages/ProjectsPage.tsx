import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FolderKanban, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { ProjectKeyBadge } from '@/features/projects/ProjectKeyBadge';
import { CreateProjectDialog } from '@/features/projects/CreateProjectDialog';
import { fetchProjects } from '@/features/projects/api';
import { useAuth } from '@/features/auth/useAuth';
import { queryKeys } from '@/lib/queryKeys';

export default function ProjectsPage() {
  const { user } = useAuth();
  const canCreate = user?.role !== 'viewer';
  const [dialogOpen, setDialogOpen] = useState(false);

  const query = useQuery({
    queryKey: queryKeys.projects.list(),
    queryFn: () => fetchProjects(false),
  });

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Projets</h1>
          <p className="text-sm text-muted-foreground">Vos projets Jirou.</p>
        </div>
        {canCreate && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Créer un projet
          </Button>
        )}
      </header>

      {query.isLoading && <ListSkeleton />}

      {query.isError && (
        <ErrorState
          description="Impossible de charger les projets."
          onRetry={() => query.refetch()}
        />
      )}

      {query.data && query.data.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="Aucun projet pour le moment"
          description="Créez votre premier projet pour commencer à organiser vos tickets."
          actionLabel={canCreate ? 'Créer un projet' : undefined}
          onAction={canCreate ? () => setDialogOpen(true) : undefined}
        />
      )}

      {query.data && query.data.length > 0 && (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {query.data.map((project) => (
            <li key={project.id}>
              <Link
                to={`/projects/${project.id}`}
                className="flex h-full flex-col gap-3 rounded-lg border border-border p-4 transition-colors hover:border-primary hover:bg-surface"
              >
                <div className="flex items-center gap-3">
                  <ProjectKeyBadge
                    projectKey={project.key}
                    color={project.color}
                  />
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{project.name}</h2>
                    <p className="font-mono text-xs text-muted-foreground">
                      {project.key}
                    </p>
                  </div>
                </div>
                {project.description && (
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {project.description}
                  </p>
                )}
                <p className="mt-auto text-xs text-muted-foreground">
                  {project.member_count} membre
                  {project.member_count > 1 ? 's' : ''}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <CreateProjectDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
