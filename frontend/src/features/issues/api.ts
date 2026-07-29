import api from '@/lib/api';
import { filenameFromDisposition, saveBlob } from '@/lib/download';
import type {
  CreateIssuePayload,
  Issue,
  IssueDetail,
  IssueFilters,
  Label,
  UpdateIssuePayload,
} from './types';

/** Retire les filtres vides avant de les passer en query params. */
function toParams(filters: IssueFilters): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== '') params[k] = v;
  }
  return params;
}

export async function createIssue(
  projectId: number | string,
  payload: CreateIssuePayload
): Promise<Issue> {
  const { data } = await api.post<Issue>(
    `/projects/${projectId}/issues`,
    payload
  );
  return data;
}

export async function fetchIssues(
  projectId: number | string,
  filters: IssueFilters = {}
): Promise<Issue[]> {
  const { data } = await api.get<Issue[]>(`/projects/${projectId}/issues`, {
    params: toParams(filters),
  });
  return data;
}

/**
 * Exporte les tickets du projet en CSV et déclenche l'enregistrement du
 * fichier. Les `filters` sont ceux de la liste : le fichier porte donc
 * exactement les tickets affichés, sans pagination. Retourne le nom utilisé.
 */
export async function exportIssuesCsv(
  projectId: number | string,
  filters: IssueFilters = {}
): Promise<string> {
  const res = await api.get(`/projects/${projectId}/issues/export`, {
    params: toParams(filters),
    responseType: 'blob',
  });
  const filename =
    filenameFromDisposition(res.headers['content-disposition'] as string) ??
    'tickets.csv';
  saveBlob(res.data as Blob, filename);
  return filename;
}

export async function fetchIssue(key: string): Promise<IssueDetail> {
  const { data } = await api.get<IssueDetail>(`/issues/${key}`);
  return data;
}

/** Tickets assignés à l'utilisateur courant, tous projets confondus. */
export async function fetchMyIssues(): Promise<Issue[]> {
  const { data } = await api.get<Issue[]>('/users/me/issues');
  return data;
}

export async function updateIssue(
  key: string,
  payload: UpdateIssuePayload
): Promise<IssueDetail> {
  const { data } = await api.patch<IssueDetail>(`/issues/${key}`, payload);
  return data;
}

export async function deleteIssue(key: string): Promise<void> {
  await api.delete(`/issues/${key}`);
}

// ---- Import CSV ----

export interface ImportResult {
  created: number;
  error_count: number;
  errors: { row: number; message: string }[];
  issues: Issue[];
}

export async function importIssuesCsv(
  projectId: number | string,
  file: File,
  epicId?: number | string | null
): Promise<ImportResult> {
  const form = new FormData();
  form.append('file', file);
  if (epicId != null && epicId !== '') form.append('epic_id', String(epicId));
  const { data } = await api.post<ImportResult>(
    `/projects/${projectId}/issues/import`,
    form,
    { headers: { 'Content-Type': undefined } }
  );
  return data;
}

// ---- Dépendances (JIR-61) ----

export async function addDependency(
  key: string,
  payload: { target_key: string; type?: string }
): Promise<unknown> {
  const { data } = await api.post(`/issues/${key}/dependencies`, payload);
  return data;
}

export async function removeDependency(
  key: string,
  dependencyId: number
): Promise<void> {
  await api.delete(`/issues/${key}/dependencies/${dependencyId}`);
}

// ---- Labels ----

export async function fetchLabels(
  projectId: number | string
): Promise<Label[]> {
  const { data } = await api.get<Label[]>(`/projects/${projectId}/labels`);
  return data;
}

export async function createLabel(
  projectId: number | string,
  payload: { name: string; color: string }
): Promise<Label> {
  const { data } = await api.post<Label>(
    `/projects/${projectId}/labels`,
    payload
  );
  return data;
}

export async function updateLabel(
  labelId: number,
  payload: { name?: string; color?: string }
): Promise<Label> {
  const { data } = await api.patch<Label>(`/labels/${labelId}`, payload);
  return data;
}

export async function deleteLabel(labelId: number): Promise<void> {
  await api.delete(`/labels/${labelId}`);
}
