import { PressureTest } from './types';

const API_BASE = '/api/v1';

export async function fetchPressureTests(query?: string): Promise<PressureTest[]> {
  const url = query && query.trim() 
    ? `${API_BASE}/tests?q=${encodeURIComponent(query.trim())}`
    : `${API_BASE}/tests`;
    
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch pressure tests (${res.status})`);
  }
  return res.json();
}

export async function fetchTestByLog(logNo: string): Promise<PressureTest> {
  const res = await fetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}`);
  if (!res.ok) {
    throw new Error(`Failed to load log ${logNo} (${res.status})`);
  }
  return res.json();
}

export function getRevisionZipUrl(logNo: string, revisionId: string): string {
  return `${API_BASE}/tests/${encodeURIComponent(logNo)}/revisions/${encodeURIComponent(revisionId)}/zip`;
}

export function getArtifactFileUrl(artifactId: string): string {
  return `${API_BASE}/tests/artifacts/${encodeURIComponent(artifactId)}/file`;
}

export async function fetchRecords(query?: string, status?: string): Promise<any[]> {
  let url = `${API_BASE}/records`;
  const params = new URLSearchParams();
  if (query && query.trim()) params.append('q', query.trim());
  if (status && status !== 'all') params.append('status', status);
  if (params.toString()) url += `?${params.toString()}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load records (${res.status})`);
  return res.json();
}

export function getRecordPdfUrl(recordId: string): string {
  return `${API_BASE}/records/${encodeURIComponent(recordId)}/pdf`;
}
