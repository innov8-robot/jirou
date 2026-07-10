import api from '@/lib/api';
import type { MiniUser } from '@/features/issues/types';

export interface ActivityEntry {
  id: number;
  action: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  actor: MiniUser | null;
  created_at: string;
}

export async function fetchActivity(key: string): Promise<ActivityEntry[]> {
  const { data } = await api.get<ActivityEntry[]>(`/issues/${key}/activity`);
  return data;
}
