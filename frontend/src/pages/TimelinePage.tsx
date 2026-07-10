import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarRange } from 'lucide-react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EmptyState } from '@/components/EmptyState';
import { ErrorState } from '@/components/ErrorState';
import { ListSkeleton } from '@/components/LoadingSkeletons';
import { TimelineChart, type Scale } from '@/features/timeline/TimelineChart';
import { fetchTimeline } from '@/features/timeline/api';
import { updateIssue } from '@/features/issues/api';
import { useProject } from '@/features/projects/useProject';
import { queryKeys } from '@/lib/queryKeys';
import { getErrorMessage, toast } from '@/lib/toast';

export default function TimelinePage() {
  const { project } = useProject();
  const canEdit = project.my_role === 'admin' || project.my_role === 'member';
  const queryClient = useQueryClient();
  const [scale, setScale] = useState<Scale>('months');

  const query = useQuery({
    queryKey: queryKeys.timeline.view(project.id),
    queryFn: () => fetchTimeline(project.id),
  });

  const mutation = useMutation({
    mutationFn: (v: { key: string; start: string; due: string }) =>
      updateIssue(v.key, { start_date: v.start, due_date: v.due }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.timeline.view(project.id),
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.issues.all });
    },
    onError: (err) => toast.error('Échec', getErrorMessage(err)),
  });

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center gap-2">
        <h1 className="text-lg font-semibold">Timeline</h1>
        <Select value={scale} onValueChange={(v) => setScale(v as Scale)}>
          <SelectTrigger className="ml-auto w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="weeks">Semaines</SelectItem>
            <SelectItem value="months">Mois</SelectItem>
            <SelectItem value="quarters">Trimestres</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {query.isLoading && <ListSkeleton />}
      {query.isError && (
        <ErrorState
          description="Impossible de charger la timeline."
          onRetry={() => query.refetch()}
        />
      )}
      {query.data && query.data.epics.length === 0 && (
        <EmptyState
          icon={CalendarRange}
          title="Aucun Epic"
          description="Créez des tickets de type Epic (avec des dates de début/fin) pour les voir sur la timeline."
        />
      )}
      {query.data && query.data.epics.length > 0 && (
        <TimelineChart
          data={query.data}
          projectId={project.id}
          scale={scale}
          canEdit={canEdit}
          onCommitDates={(key, start, due) =>
            mutation.mutate({ key, start, due })
          }
        />
      )}
    </div>
  );
}
