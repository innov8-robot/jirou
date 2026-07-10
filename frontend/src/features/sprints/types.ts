import type { Issue } from '@/features/issues/types';

export type SprintStatus = 'future' | 'active' | 'completed';

export interface Sprint {
  id: number | string;
  project_id: number | string;
  name: string;
  goal: string | null;
  status: SprintStatus;
  start_date: string | null;
  end_date: string | null;
  order: number;
  completed_at: string | null;
  committed_points: number;
  completed_points: number;
  issue_count: number;
}

export interface BacklogBucket {
  issues: Issue[];
  points: number;
}

export interface BacklogData {
  backlog: BacklogBucket;
  sprints: { sprint: Sprint; issues: Issue[]; points: number }[];
}

export interface SprintCompleteResult {
  sprint: Sprint;
  completed_points: number;
  committed_points: number;
  done_count: number;
  not_done_count: number;
  moved_to: string;
}

export interface VelocityPoint {
  sprint_id: number | string;
  name: string;
  committed_points: number;
  completed_points: number;
}
