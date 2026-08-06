import api from '@/lib/api';
import { filenameFromDisposition, saveBlob } from '@/lib/download';
import type { MiniUser } from '@/features/issues/types';

export type WatchStatus =
  | 'to_test'
  | 'in_progress'
  | 'promising'
  | 'abandoned';

export const WATCH_STATUS_META: Record<
  WatchStatus,
  { label: string; color: string }
> = {
  to_test: { label: 'À tester', color: '#8993A4' },
  in_progress: { label: 'En cours', color: '#3B82F6' },
  promising: { label: 'Concluant', color: '#22C55E' },
  abandoned: { label: 'Abandonné', color: '#EF4444' },
};

export const WATCH_STATUSES: WatchStatus[] = [
  'to_test',
  'in_progress',
  'promising',
  'abandoned',
];

export type WatchNodeType = 'theme' | 'techno' | 'solution' | 'resource';

export const WATCH_TYPES: WatchNodeType[] = [
  'theme',
  'techno',
  'solution',
  'resource',
];

export const WATCH_TYPE_META: Record<
  WatchNodeType,
  { label: string; color: string }
> = {
  theme: { label: 'Thème', color: '#6D5AE6' },
  techno: { label: 'Techno', color: '#3B82F6' },
  solution: { label: 'Solution', color: '#22C55E' },
  resource: { label: 'Ressource', color: '#F59E0B' },
};

export interface WatchMediaPreview {
  media_id: number;
  kind: 'image' | 'video' | 'link';
  url: string | null;
  download_url: string | null;
  content_type: string | null;
}

export interface WatchNodeSummary {
  id: number;
  parent_id: number | null;
  title: string;
  type: WatchNodeType;
  status: WatchStatus | null;
  pos_x: number;
  pos_y: number;
  media_count: number;
  comment_count: number;
  preview: WatchMediaPreview | null;
}

export interface WatchMedia {
  id: number;
  node_id: number;
  kind: 'image' | 'video' | 'link';
  filename: string | null;
  content_type: string | null;
  size: number | null;
  url: string | null;
  title: string | null;
  download_url: string | null;
  created_at: string;
}

export interface WatchNode {
  id: number;
  parent_id: number | null;
  title: string;
  type: WatchNodeType;
  note: string;
  status: WatchStatus | null;
  pos_x: number;
  pos_y: number;
  created_by: MiniUser | null;
  created_at: string;
  updated_at: string;
  media: WatchMedia[];
}

export interface WatchComment {
  id: number;
  node_id: number;
  author: MiniUser | null;
  body: string;
  created_at: string;
  updated_at: string;
}

// ---- Nœuds ----
export async function fetchNodes(): Promise<WatchNodeSummary[]> {
  const { data } = await api.get<WatchNodeSummary[]>('/watch/nodes');
  return data;
}
export async function fetchNode(id: number): Promise<WatchNode> {
  const { data } = await api.get<WatchNode>(`/watch/nodes/${id}`);
  return data;
}
export async function createNode(payload: {
  title: string;
  type?: WatchNodeType;
  parent_id?: number | null;
  note?: string;
  status?: WatchStatus | null;
  pos_x?: number;
  pos_y?: number;
}): Promise<WatchNode> {
  const { data } = await api.post<WatchNode>('/watch/nodes', payload);
  return data;
}
export async function updateNode(
  id: number,
  payload: Partial<{
    title: string;
    type: WatchNodeType;
    note: string;
    status: WatchStatus | null;
    parent_id: number | null;
    pos_x: number;
    pos_y: number;
  }>
): Promise<WatchNode> {
  const { data } = await api.patch<WatchNode>(`/watch/nodes/${id}`, payload);
  return data;
}
export async function deleteNode(id: number): Promise<void> {
  await api.delete(`/watch/nodes/${id}`);
}

// ---- Médias ----
export async function uploadMedia(
  nodeId: number,
  file: File
): Promise<WatchMedia> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<WatchMedia>(
    `/watch/nodes/${nodeId}/media`,
    form,
    { headers: { 'Content-Type': undefined } }
  );
  return data;
}
export async function addMediaLink(
  nodeId: number,
  payload: { url: string; title?: string }
): Promise<WatchMedia> {
  const { data } = await api.post<WatchMedia>(
    `/watch/nodes/${nodeId}/media/link`,
    payload
  );
  return data;
}
export async function deleteMedia(id: number): Promise<void> {
  await api.delete(`/watch/media/${id}`);
}
export async function fetchMediaBlobUrl(id: number): Promise<string> {
  const res = await api.get(`/watch/media/${id}/download`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(res.data as Blob);
}

// ---- Export / import (archive ZIP) ----
export interface WatchCsvError {
  row: number;
  message: string;
}

export interface WatchCsvImportResult {
  anchor_id: number;
  nodes_created: number;
  links_created: number;
  error_count: number;
  errors: WatchCsvError[];
}

/**
 * Télécharge l'archive ZIP de la veille (arbre + médias) et déclenche
 * l'enregistrement du fichier. Retourne le nom utilisé.
 *
 * C'est une **sauvegarde** : il n'y a pas d'import d'archive correspondant.
 * L'ajout de contenu se fait par `importWatchCsv`, ancré sous un nœud.
 */
export async function exportWatchArchive(): Promise<string> {
  const res = await api.get('/watch/export', { responseType: 'blob' });
  const filename =
    filenameFromDisposition(res.headers['content-disposition'] as string) ??
    'veille.zip';
  saveBlob(res.data as Blob, filename);
  return filename;
}

/**
 * Greffe des sous-nœuds sous `nodeId` depuis un CSV.
 * En-tête : `title,parent,type,status,note,links` — seul `title` est requis.
 */
export async function importWatchCsv(
  nodeId: number,
  file: File
): Promise<WatchCsvImportResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<WatchCsvImportResult>(
    `/watch/nodes/${nodeId}/import`,
    form,
    { headers: { 'Content-Type': undefined } }
  );
  return data;
}

// ---- Commentaires ----
export async function fetchWatchComments(
  nodeId: number
): Promise<WatchComment[]> {
  const { data } = await api.get<WatchComment[]>(
    `/watch/nodes/${nodeId}/comments`
  );
  return data;
}
export async function createWatchComment(
  nodeId: number,
  body: string
): Promise<WatchComment> {
  const { data } = await api.post<WatchComment>(
    `/watch/nodes/${nodeId}/comments`,
    { body }
  );
  return data;
}
export async function deleteWatchComment(id: number): Promise<void> {
  await api.delete(`/watch/comments/${id}`);
}
