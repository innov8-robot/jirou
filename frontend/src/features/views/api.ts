import api from '@/lib/api';

export interface SavedView {
  id: number;
  name: string;
  filters: Record<string, unknown>;
  project_id: number | string;
}

export async function fetchViews(
  projectId: number | string
): Promise<SavedView[]> {
  const { data } = await api.get<SavedView[]>(`/projects/${projectId}/views`);
  return data;
}

export async function createView(
  projectId: number | string,
  payload: { name: string; filters: Record<string, unknown> }
): Promise<SavedView> {
  const { data } = await api.post<SavedView>(
    `/projects/${projectId}/views`,
    payload
  );
  return data;
}

export async function deleteView(viewId: number): Promise<void> {
  await api.delete(`/views/${viewId}`);
}
