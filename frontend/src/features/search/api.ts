import api from '@/lib/api';
import type { IssueStatus, IssueType } from '@/lib/issues';

export interface SearchIssue {
  key: string;
  summary: string;
  type: IssueType;
  status: IssueStatus;
  project_id: number | string;
}

export interface SearchProject {
  id: number | string;
  name: string;
  key: string;
  color: string | null;
}

export interface SearchResults {
  issues: SearchIssue[];
  projects: SearchProject[];
}

export async function fetchSearch(q: string): Promise<SearchResults> {
  const { data } = await api.get<SearchResults>('/search', {
    params: { q, limit: 20 },
  });
  return data;
}
