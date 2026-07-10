import api from '@/lib/api';
import type { Issue } from '@/features/issues/types';

export interface TimelineEpic {
  epic: Issue;
  children: Issue[];
  progress: { done: number; total: number };
}

export interface TimelineDependency {
  from_key: string;
  to_key: string;
}

export interface TimelineData {
  epics: TimelineEpic[];
  dependencies: TimelineDependency[];
}

export async function fetchTimeline(
  projectId: number | string
): Promise<TimelineData> {
  const { data } = await api.get<TimelineData>(
    `/projects/${projectId}/timeline`
  );
  return data;
}
