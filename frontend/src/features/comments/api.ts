import api from '@/lib/api';
import type { MiniUser } from '@/features/issues/types';

export interface Comment {
  id: number;
  issue_id: number | string;
  author: MiniUser;
  body: string;
  created_at: string;
  updated_at: string;
}

export async function fetchComments(key: string): Promise<Comment[]> {
  const { data } = await api.get<Comment[]>(`/issues/${key}/comments`);
  return data;
}

export async function createComment(
  key: string,
  payload: { body: string; mention_user_ids?: number[] }
): Promise<Comment> {
  const { data } = await api.post<Comment>(`/issues/${key}/comments`, payload);
  return data;
}

export async function updateComment(
  id: number,
  payload: { body: string }
): Promise<Comment> {
  const { data } = await api.patch<Comment>(`/comments/${id}`, payload);
  return data;
}

export async function deleteComment(id: number): Promise<void> {
  await api.delete(`/comments/${id}`);
}
