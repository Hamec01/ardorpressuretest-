import { PressureTest, PressureTestRecord, RecordLogArtifact, TestRevision } from './types';

const API_BASE = '/api/v1';

export interface ResolvedPtrSource {
  pressure_test_id: string;
  test_revision_id: string;
  log_no: string;
  revision_id: string;
  operator: string;
  metadata: TestRevision['metadata_json'];
  metrics: TestRevision['metrics_json'];
  pipecloud_added: boolean;
  selected_pipe_numbers: string[];
  artifacts: RecordLogArtifact[];
}

export async function resolvePtrSources(identifiers: string[]): Promise<{ matches: ResolvedPtrSource[]; unmatched_identifiers: string[] }> {
  const res = await fetch(`${API_BASE}/tests/resolve-ptr-sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifiers }),
  });
  if (!res.ok) throw new Error(`Failed to resolve PTR sources (${res.status})`);
  return res.json();
}

export async function fetchPtrSourceIdentifiers(query = ''): Promise<{ pipes: string[]; bundles: string[] }> {
  const res = await fetch(`${API_BASE}/tests/ptr-source-identifiers?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Failed to load PTR source identifiers (${res.status})`);
  return res.json();
}

export async function fetchPressureTests(query?: string, pipecloudFilter?: string): Promise<PressureTest[]> {
  const params = new URLSearchParams();
  if (query && query.trim()) params.append('q', query.trim());
  if (pipecloudFilter && pipecloudFilter !== 'all') params.append('pipecloud_filter', pipecloudFilter);

  const qs = params.toString();
  const url = qs ? `${API_BASE}/tests?${qs}` : `${API_BASE}/tests`;
    
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch pressure tests (${res.status})`);
  }
  return res.json();
}

export async function fetchTrash(): Promise<PressureTest[]> {
  const res = await fetch(`${API_BASE}/tests/trash`);
  if (!res.ok) throw new Error(`Failed to fetch trash (${res.status})`);
  return res.json();
}

export async function restorePressureTest(logNo: string, token?: string | null): Promise<PressureTest> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/restore`, { method: 'POST', headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to restore test (${res.status})`);
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

export async function updatePipeCloudStatus(
  logNo: string,
  added: boolean,
  token?: string | null,
  idempotencyKey?: string
): Promise<{ log_no: string; pipecloud_added: boolean; pipecloud_updated_at?: string; pipecloud_updated_by_name?: string }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/pipecloud`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ added, idempotency_key: idempotencyKey })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update PipeCloud status (${res.status})`);
  }
  return res.json();
}

export function getRevisionZipUrl(logNo: string, revisionId: string): string {
  return `${API_BASE}/tests/${encodeURIComponent(logNo)}/revisions/${encodeURIComponent(revisionId)}/zip`;
}

export function getArtifactFileUrl(artifactId: string): string {
  return `${API_BASE}/tests/artifacts/${encodeURIComponent(artifactId)}/file`;
}

export async function deleteArtifact(artifactId: string, token?: string | null): Promise<PressureTest> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/tests/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete artifact (${res.status})`);
  }
  return res.json();
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

export function getRecordFullPdfUrl(recordId: string): string {
  return `${API_BASE}/records/${encodeURIComponent(recordId)}/full-pdf`;
}

export async function estimateRecordPages(recordId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/records/${encodeURIComponent(recordId)}/estimate-pages`);
  if (!res.ok) throw new Error(`Failed to estimate record pages (${res.status})`);
  return res.json();
}

export async function deleteRecord(recordId: string, token?: string | null): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/records/${encodeURIComponent(recordId)}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete record (${res.status})`);
  }
}

export async function updateRecord(recordId: string, payload: Record<string, unknown>, token?: string | null): Promise<PressureTestRecord> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/records/${encodeURIComponent(recordId)}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update record (${res.status})`);
  }
  return res.json();
}

export async function unconfirmRecord(recordId: string, token?: string | null): Promise<PressureTestRecord> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/records/${encodeURIComponent(recordId)}/unconfirm`, { method: 'POST', headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to revoke confirmation (${res.status})`);
  }
  return res.json();
}

export async function deletePressureTest(logNo: string, token?: string | null): Promise<void> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete test (${res.status})`);
  }
}
