import api from '@/lib/api';
import type { MiniUser } from '@/features/issues/types';

export interface Attachment {
  id: number;
  issue_id: number | string;
  filename: string;
  content_type: string;
  size: number;
  uploaded_by: MiniUser;
  created_at: string;
  download_url: string;
}

export async function fetchAttachments(key: string): Promise<Attachment[]> {
  const { data } = await api.get<Attachment[]>(`/issues/${key}/attachments`);
  return data;
}

export async function uploadAttachment(
  key: string,
  file: File
): Promise<Attachment> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<Attachment>(
    `/issues/${key}/attachments`,
    form,
    // Laisse axios poser le Content-Type multipart + boundary.
    { headers: { 'Content-Type': undefined } }
  );
  return data;
}

export async function deleteAttachment(id: number): Promise<void> {
  await api.delete(`/attachments/${id}`);
}

/** Récupère le fichier (avec Bearer) sous forme de blob object-URL. */
export async function fetchAttachmentBlobUrl(id: number): Promise<string> {
  const res = await api.get(`/attachments/${id}/download`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(res.data as Blob);
}

/** Déclenche le téléchargement du fichier dans le navigateur. */
export async function downloadAttachment(att: Attachment): Promise<void> {
  const url = await fetchAttachmentBlobUrl(att.id);
  const a = document.createElement('a');
  a.href = url;
  a.download = att.filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
