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
