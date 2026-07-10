import api from '@/lib/api';
import type { ProjectRole } from './types';
import type {
  CreateProjectPayload,
  Project,
  ProjectDetail,
  ProjectMember,
  UpdateProjectPayload,
} from './types';

export async function fetchProjects(
  includeArchived = false
): Promise<Project[]> {
  const { data } = await api.get<Project[]>('/projects', {
    params: { include_archived: includeArchived },
  });
  return data;
}

export async function fetchProject(
  id: number | string
): Promise<ProjectDetail> {
  const { data } = await api.get<ProjectDetail>(`/projects/${id}`);
  return data;
}

export async function createProject(
  payload: CreateProjectPayload
): Promise<Project> {
  const { data } = await api.post<Project>('/projects', payload);
  return data;
}

export async function updateProject(
  id: number | string,
  payload: UpdateProjectPayload
): Promise<Project> {
  const { data } = await api.patch<Project>(`/projects/${id}`, payload);
  return data;
}

/** Archivage logique (DELETE → is_archived=true). */
export async function archiveProject(id: number | string): Promise<void> {
  await api.delete(`/projects/${id}`);
}

export async function fetchMembers(
  id: number | string
): Promise<ProjectMember[]> {
  const { data } = await api.get<ProjectMember[]>(`/projects/${id}/members`);
  return data;
}

export async function addMember(
  id: number | string,
  payload: { email: string; role: ProjectRole }
): Promise<ProjectMember> {
  const { data } = await api.post<ProjectMember>(
    `/projects/${id}/members`,
    payload
  );
  return data;
}

export async function updateMember(
  id: number | string,
  userId: number | string,
  payload: { role: ProjectRole }
): Promise<ProjectMember> {
  const { data } = await api.patch<ProjectMember>(
    `/projects/${id}/members/${userId}`,
    payload
  );
  return data;
}

export async function removeMember(
  id: number | string,
  userId: number | string
): Promise<void> {
  await api.delete(`/projects/${id}/members/${userId}`);
}
