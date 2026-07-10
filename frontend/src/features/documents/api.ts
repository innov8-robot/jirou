import api from '@/lib/api';
import type { MiniUser } from '@/features/issues/types';

export interface DocumentSummary {
  id: number;
  project_id: number | string;
  title: string;
  author: MiniUser | null;
  updated_at: string;
}

export interface DocumentRead extends DocumentSummary {
  content: string;
  created_at: string;
}

export interface ProjectMini {
  id: number | string;
  name: string;
  key: string;
}

export interface GlobalDocumentSummary {
  id: number;
  title: string;
  author: MiniUser | null;
  updated_at: string;
  project: ProjectMini | null;
}

/** Tous les documents visibles : généraux + ceux des projets où l'on est membre. */
export async function fetchAllDocuments(): Promise<GlobalDocumentSummary[]> {
  const { data } = await api.get<GlobalDocumentSummary[]>('/documents');
  return data;
}

/** Crée un document général (non lié à un projet). */
export async function createGeneralDocument(payload: {
  title: string;
  content?: string;
}): Promise<DocumentRead> {
  const { data } = await api.post<DocumentRead>('/documents', payload);
  return data;
}

export async function fetchDocuments(
  projectId: number | string
): Promise<DocumentSummary[]> {
  const { data } = await api.get<DocumentSummary[]>(
    `/projects/${projectId}/documents`
  );
  return data;
}

export async function fetchDocument(id: number): Promise<DocumentRead> {
  const { data } = await api.get<DocumentRead>(`/documents/${id}`);
  return data;
}

export async function createDocument(
  projectId: number | string,
  payload: { title: string; content?: string }
): Promise<DocumentRead> {
  const { data } = await api.post<DocumentRead>(
    `/projects/${projectId}/documents`,
    payload
  );
  return data;
}

export async function updateDocument(
  id: number,
  payload: { title?: string; content?: string }
): Promise<DocumentRead> {
  const { data } = await api.patch<DocumentRead>(`/documents/${id}`, payload);
  return data;
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`);
}
