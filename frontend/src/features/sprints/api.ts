import api from '@/lib/api';
import type { Issue, IssueFilters } from '@/features/issues/types';
import type {
  BacklogData,
  Sprint,
  SprintCompleteResult,
  VelocityPoint,
} from './types';

export async function fetchSprints(
  projectId: number | string,
  includeCompleted = false
): Promise<Sprint[]> {
  const { data } = await api.get<Sprint[]>(`/projects/${projectId}/sprints`, {
    params: { include_completed: includeCompleted },
  });
  return data;
}

export async function createSprint(
  projectId: number | string,
  payload: { name: string; goal?: string }
): Promise<Sprint> {
  const { data } = await api.post<Sprint>(
    `/projects/${projectId}/sprints`,
    payload
  );
  return data;
}

export async function updateSprint(
  sprintId: number | string,
  payload: {
    name?: string;
    goal?: string | null;
    start_date?: string | null;
    end_date?: string | null;
  }
): Promise<Sprint> {
  const { data } = await api.patch<Sprint>(`/sprints/${sprintId}`, payload);
  return data;
}

export async function startSprint(
  sprintId: number | string,
  payload: { start_date?: string | null; end_date?: string | null }
): Promise<Sprint> {
  const { data } = await api.post<Sprint>(`/sprints/${sprintId}/start`, payload);
  return data;
}

export async function completeSprint(
  sprintId: number | string,
  payload: { move_incomplete_to?: 'backlog' | 'next' }
): Promise<SprintCompleteResult> {
  const { data } = await api.post<SprintCompleteResult>(
    `/sprints/${sprintId}/complete`,
    payload
  );
  return data;
}

export async function deleteSprint(sprintId: number | string): Promise<void> {
  await api.delete(`/sprints/${sprintId}`);
}

export async function fetchBacklog(
  projectId: number | string,
  filters: IssueFilters = {}
): Promise<BacklogData> {
  const params: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== '') params[k] = v;
  }
  const { data } = await api.get<BacklogData>(
    `/projects/${projectId}/backlog`,
    { params }
  );
  return data;
}

export async function backlogMove(
  key: string,
  payload: { sprint_id: number | string | null; position: number }
): Promise<Issue> {
  const { data } = await api.patch<Issue>(`/issues/${key}/backlog-move`, payload);
  return data;
}

export async function fetchVelocity(
  projectId: number | string
): Promise<VelocityPoint[]> {
  const { data } = await api.get<VelocityPoint[]>(
    `/projects/${projectId}/velocity`
  );
  return data;
}
