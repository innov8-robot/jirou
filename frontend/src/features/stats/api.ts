import api from '@/lib/api';
import type { Issue, MiniUser } from '@/features/issues/types';
import type { Sprint } from '@/features/sprints/types';
import type { IssueStatus, IssueType } from '@/lib/issues';

export interface ProjectStats {
  total: number;
  by_status: Record<IssueStatus, number>;
  by_type: Record<IssueType, number>;
  by_assignee: { user: MiniUser | null; count: number }[];
  recent: Issue[];
  active_sprint: {
    sprint: Sprint;
    done: number;
    total: number;
    points_done: number;
    points_total: number;
  } | null;
}

export async function fetchProjectStats(
  projectId: number | string
): Promise<ProjectStats> {
  const { data } = await api.get<ProjectStats>(`/projects/${projectId}/stats`);
  return data;
}
