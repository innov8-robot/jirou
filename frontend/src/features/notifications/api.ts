import api from '@/lib/api';
import type { MiniUser } from '@/features/issues/types';

export type NotificationType = 'mention' | 'assignment';

export interface Notification {
  id: number;
  type: NotificationType;
  message: string;
  is_read: boolean;
  created_at: string;
  actor: MiniUser | null;
  issue_key: string | null;
  project_id: number | string | null;
}

export async function fetchNotifications(
  unreadOnly = false
): Promise<Notification[]> {
  const { data } = await api.get<Notification[]>('/notifications', {
    params: { unread_only: unreadOnly, limit: 50 },
  });
  return data;
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>(
    '/notifications/unread-count'
  );
  return data.count;
}

export async function markRead(id: number): Promise<void> {
  await api.patch(`/notifications/${id}/read`);
}

export async function markAllRead(): Promise<void> {
  await api.post('/notifications/read-all');
}
