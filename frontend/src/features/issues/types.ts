import type { IssueStatus, IssueType, Priority } from '@/lib/issues';
import type { UserRole } from '@/features/auth/types';

export interface MiniUser {
  id: number | string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: UserRole;
}

export interface Label {
  id: number;
  name: string;
  color: string;
  project_id: number | string;
}

export interface Issue {
  id: number | string;
  key: string;
  project_id: number | string;
  type: IssueType;
  summary: string;
  status: IssueStatus;
  priority: Priority;
  story_points: number | null;
  assignee_id: number | string | null;
  reporter_id: number | string;
  epic_id: number | string | null;
  start_date: string | null;
  due_date: string | null;
  position: number;
  created_at: string;
  updated_at: string;
  labels: Label[];
  assignee: MiniUser | null;
  reporter: MiniUser;
}

export interface MiniIssue {
  id: number | string;
  key: string;
  summary: string;
  type: IssueType;
  status: IssueStatus;
}

export type DependencyDirection = 'outward' | 'inward';

export interface DependencyLink {
  id: number;
  type: string;
  direction: DependencyDirection;
  issue: MiniIssue;
}

export interface IssueDetail extends Issue {
  description: string | null;
  children: Issue[];
  progress: { done: number; total: number } | null;
  dependencies?: DependencyLink[];
}

export interface IssueFilters {
  type?: IssueType;
  status?: IssueStatus;
  assignee_id?: number | string;
  label_id?: number;
  epic_id?: number | string;
  sprint_id?: number | string;
  search?: string;
  sort?: string;
}

export interface CreateIssuePayload {
  type: IssueType;
  summary: string;
  description?: string | null;
  priority?: Priority;
  story_points?: number | null;
  assignee_id?: number | string | null;
  epic_id?: number | string | null;
  start_date?: string | null;
  due_date?: string | null;
  label_ids?: number[];
}

export interface UpdateIssuePayload {
  type?: IssueType;
  summary?: string;
  description?: string | null;
  status?: IssueStatus;
  priority?: Priority;
  story_points?: number | null;
  assignee_id?: number | string | null;
  epic_id?: number | string | null;
  start_date?: string | null;
  due_date?: string | null;
  position?: number;
  label_ids?: number[];
}
