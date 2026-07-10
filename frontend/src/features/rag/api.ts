import api from '@/lib/api';

export interface RagSource {
  kind: 'issue' | 'comment' | 'document';
  project_id: number | string | null;
  issue_key: string | null;
  title: string;
}

export interface RagAnswer {
  answer: string;
  sources: RagSource[];
}

export async function ragStatus(): Promise<{ enabled: boolean }> {
  const { data } = await api.get<{ enabled: boolean }>('/rag/status');
  return data;
}

export async function ragChat(question: string): Promise<RagAnswer> {
  const { data } = await api.post<RagAnswer>('/rag/chat', { question });
  return data;
}

export async function ragReindex(): Promise<{ indexed: number }> {
  const { data } = await api.post<{ indexed: number }>('/rag/reindex');
  return data;
}
