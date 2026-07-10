import api from '@/lib/api';
import type { Issue, IssueFilters } from '@/features/issues/types';
import type { IssueStatus } from '@/lib/issues';

export interface BoardColumn {
  status: IssueStatus;
  issues: Issue[];
}

export interface BoardData {
  columns: BoardColumn[];
}

export async function fetchBoard(
  projectId: number | string,
  filters: IssueFilters = {}
): Promise<BoardData> {
  const params: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== '') params[k] = v;
  }
  const { data } = await api.get<BoardData>(`/projects/${projectId}/board`, {
    params,
  });
  return data;
}

export async function moveIssue(
  key: string,
  payload: { status: IssueStatus; position: number }
): Promise<Issue> {
  const { data } = await api.patch<Issue>(`/issues/${key}/move`, payload);
  return data;
}
