import api from '@/lib/api';

export interface ReportResult {
  project_id: number | string | null;
  generated_at: string;
  llm_used: boolean;
  markdown: string;
}

export async function generateReport(
  projectId?: number | string | null
): Promise<ReportResult> {
  const { data } = await api.post<ReportResult>('/reports/generate', {
    project_id: projectId ?? null,
  });
  return data;
}
