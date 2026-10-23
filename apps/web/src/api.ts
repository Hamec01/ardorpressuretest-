import { Account, AccountRole, IssuedPasswordLink, PasswordLinkInfo, PublicLog, ShareLink, PlannedTestList, PlannedTestListDetail, PlannedTestPriority, PressureTest, PressureTestRecord, RecordLogArtifact, TestRevision } from './types';
import { authFetch, publicFetch } from './authFetch';

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
  pipe_source_data: Record<string, Record<string, string>>;
  artifacts: RecordLogArtifact[];
}

export async function resolvePtrSources(identifiers: string[]): Promise<{ matches: ResolvedPtrSource[]; unmatched_identifiers: string[] }> {
  const res = await authFetch(`${API_BASE}/tests/resolve-ptr-sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifiers }),
  });
  if (!res.ok) throw new Error(`Failed to resolve PTR sources (${res.status})`);
  return res.json();
}

export async function fetchPtrSourceIdentifiers(query = ''): Promise<{ pipes: string[]; bundles: string[] }> {
  const res = await authFetch(`${API_BASE}/tests/ptr-source-identifiers?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Failed to load PTR source identifiers (${res.status})`);
  return res.json();
}

export interface PressureTestFilters {
  logNo: string;
  testDate: string;
  operator: string;
  bundle: string;
  pipe: string;
}

export const EMPTY_PRESSURE_TEST_FILTERS: PressureTestFilters = {
  logNo: '',
  testDate: '',
  operator: '',
  bundle: '',
  pipe: '',
};

/** Matches MAX_LIST_LIMIT in services/api/routes/tests.py. */
export const ALL_TESTS_LIMIT = 10000;

export async function fetchPressureTests(query?: string, pipecloudFilter?: string, filters: PressureTestFilters = EMPTY_PRESSURE_TEST_FILTERS): Promise<PressureTest[]> {
  const params = new URLSearchParams();
  if (query && query.trim()) params.append('q', query.trim());
  if (pipecloudFilter && pipecloudFilter !== 'all') params.append('pipecloud_filter', pipecloudFilter);
  if (filters.logNo.trim()) params.append('log_no', filters.logNo.trim());
  if (filters.testDate) params.append('test_date', filters.testDate);
  if (filters.operator.trim()) params.append('operator', filters.operator.trim());
  if (filters.bundle.trim()) params.append('bundle', filters.bundle.trim());
  if (filters.pipe.trim()) params.append('pipe', filters.pipe.trim());
  // Load every log: the list and the statistics must not stop at the API default of 50.
  params.append('limit', String(ALL_TESTS_LIMIT));

  const qs = params.toString();
  const url = qs ? `${API_BASE}/tests?${qs}` : `${API_BASE}/tests`;
    
  const res = await authFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch pressure tests (${res.status})`);
  }
  return res.json();
}

export async function fetchTrash(): Promise<PressureTest[]> {
  const res = await authFetch(`${API_BASE}/tests/trash`);
  if (!res.ok) throw new Error(`Failed to fetch trash (${res.status})`);
  return res.json();
}

export async function restorePressureTest(logNo: string): Promise<PressureTest> {
  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/restore`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to restore test (${res.status})`);
  }
  return res.json();
}

export async function permanentlyDeletePressureTest(logNo: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/permanent`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to permanently delete test (${res.status})`);
  }
}

export async function deleteTestRevision(logNo: string, revisionId: string): Promise<PressureTest> {
  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/revisions/${encodeURIComponent(revisionId)}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to remove revision (${res.status})`);
  }
  return res.json();
}

export async function fetchPlannedTestLists(query = ''): Promise<PlannedTestList[]> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Failed to load pressure test plans (${res.status})`);
  return res.json();
}

export async function createPlannedTestList(name: string, description: string, priority: PlannedTestPriority = 0): Promise<{ id: string }> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, priority }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create pressure test plan (${res.status})`);
  }
  return res.json();
}

export async function updatePlannedTestList(listId: string, payload: { name?: string; description?: string; priority?: PlannedTestPriority }): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists/${encodeURIComponent(listId)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update pressure test plan (${res.status})`);
  }
}

export async function deletePlannedTestList(listId: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists/${encodeURIComponent(listId)}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete pressure test plan (${res.status})`);
  }
}

export async function fetchPlannedTestPipes(listId: string, query = ''): Promise<PlannedTestListDetail> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists/${encodeURIComponent(listId)}/pipes?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error(`Failed to load planned pipes (${res.status})`);
  return res.json();
}

export async function addPlannedTestPipes(listId: string, inputText: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists/${encodeURIComponent(listId)}/pipes/bulk`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input_text: inputText }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(typeof err.detail === 'string' ? err.detail : err.detail?.message || `Failed to add planned pipes (${res.status})`);
  }
}

export async function updatePlannedTestPipe(pipeId: string, pipeNumber: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/pipes/${encodeURIComponent(pipeId)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pipe_number: pipeNumber }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update planned pipe (${res.status})`);
  }
}

export async function deletePlannedTestPipe(pipeId: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/pipes/${encodeURIComponent(pipeId)}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete planned pipe (${res.status})`);
  }
}

export async function deletePlannedTestBundle(listId: string, bundleNumber: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/planned-tests/lists/${encodeURIComponent(listId)}/bundles/${encodeURIComponent(bundleNumber)}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete planned bundle (${res.status})`);
  }
}

export async function fetchTestByLog(logNo: string): Promise<PressureTest> {
  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}`);
  if (!res.ok) {
    throw new Error(`Failed to load log ${logNo} (${res.status})`);
  }
  return res.json();
}

export async function updatePipeCloudStatus(
  logNo: string,
  added: boolean,
  idempotencyKey?: string
): Promise<{ log_no: string; pipecloud_added: boolean; pipecloud_updated_at?: string; pipecloud_updated_by_name?: string }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };

  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}/pipecloud`, {
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

export function getArtifactThumbnailUrl(artifactId: string): string {
  return `${API_BASE}/tests/artifacts/${encodeURIComponent(artifactId)}/thumbnail`;
}

export async function deleteArtifact(artifactId: string): Promise<PressureTest> {
  const res = await authFetch(`${API_BASE}/tests/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'DELETE',
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

  const res = await authFetch(url);
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
  const res = await authFetch(`${API_BASE}/records/${encodeURIComponent(recordId)}/estimate-pages`);
  if (!res.ok) throw new Error(`Failed to estimate record pages (${res.status})`);
  return res.json();
}

export async function deleteRecord(recordId: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/records/${encodeURIComponent(recordId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete record (${res.status})`);
  }
}

export async function updateRecord(recordId: string, payload: Record<string, unknown>): Promise<PressureTestRecord> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const res = await authFetch(`${API_BASE}/records/${encodeURIComponent(recordId)}`, {
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

export async function unconfirmRecord(recordId: string): Promise<PressureTestRecord> {
  const res = await authFetch(`${API_BASE}/records/${encodeURIComponent(recordId)}/unconfirm`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to revoke confirmation (${res.status})`);
  }
  return res.json();
}

export async function deletePressureTest(logNo: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/tests/${encodeURIComponent(logNo)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to delete test (${res.status})`);
  }
}


// ---- Admin account management (docs/ACCESS_PLAN_R4-R7.md stage 1) ----

/** Error carrying the HTTP status so the UI can show a translated message. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  const detail = typeof body?.detail === 'string' ? body.detail : `HTTP ${res.status}`;
  return new ApiError(res.status, detail);
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) throw await apiError(res);
  return res.json();
}

export async function fetchAccounts(): Promise<Account[]> {
  return jsonOrThrow(await authFetch(`${API_BASE}/auth/users`));
}

export interface AccountCreatePayload {
  username: string;
  full_name: string;
  email?: string | null;
  role: AccountRole;
  password?: string | null;
  require_password_change?: boolean;
}

export async function createAccount(payload: AccountCreatePayload): Promise<{ account: Account; password_link: IssuedPasswordLink | null }> {
  return jsonOrThrow(await authFetch(`${API_BASE}/auth/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function updateAccount(
  id: string,
  changes: { full_name?: string; email?: string | null; role?: AccountRole; is_active?: boolean },
): Promise<Account> {
  return jsonOrThrow(await authFetch(`${API_BASE}/auth/users/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  }));
}

export async function createPasswordLink(id: string): Promise<IssuedPasswordLink> {
  return jsonOrThrow(await authFetch(`${API_BASE}/auth/users/${encodeURIComponent(id)}/password-link`, { method: 'POST' }));
}

export async function setAccountPassword(id: string, password: string, requirePasswordChange: boolean): Promise<Account> {
  return jsonOrThrow(await authFetch(`${API_BASE}/auth/users/${encodeURIComponent(id)}/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password, require_password_change: requirePasswordChange }),
  }));
}

/** Public: the link token itself authorises these two calls. */
export async function fetchPasswordLink(token: string): Promise<PasswordLinkInfo> {
  return jsonOrThrow(await publicFetch(`${API_BASE}/auth/password-links/${encodeURIComponent(token)}`));
}

export async function submitPasswordLink(token: string, newPassword: string): Promise<{ status: string; username: string }> {
  return jsonOrThrow(await publicFetch(`${API_BASE}/auth/password-links/${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_password: newPassword }),
  }));
}


// ---- Public share links (docs/ACCESS_PLAN_R4-R7.md stage 2) ----

export async function createShare(logNo: string): Promise<ShareLink> {
  return jsonOrThrow(await authFetch(`${API_BASE}/shares`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ log_no: logNo }),
  }));
}

export async function fetchShares(logNo: string): Promise<ShareLink[]> {
  return jsonOrThrow(await authFetch(`${API_BASE}/shares?log_no=${encodeURIComponent(logNo)}`));
}

export async function revokeShare(id: string): Promise<ShareLink> {
  return jsonOrThrow(await authFetch(`${API_BASE}/shares/${encodeURIComponent(id)}`, { method: 'DELETE' }));
}

export async function fetchPublicShare(token: string): Promise<PublicLog> {
  return jsonOrThrow(await publicFetch(`${API_BASE}/public/shares/${encodeURIComponent(token)}`));
}

export async function resolveLegacyShare(logNo: string): Promise<{ token: string }> {
  return jsonOrThrow(await publicFetch(`${API_BASE}/public/legacy/${encodeURIComponent(logNo)}`));
}

export function publicArtifactUrl(token: string, artifactId: string): string {
  return `${API_BASE}/public/shares/${encodeURIComponent(token)}/artifacts/${encodeURIComponent(artifactId)}`;
}

export function publicArtifactThumbnailUrl(token: string, artifactId: string): string {
  return `${API_BASE}/public/shares/${encodeURIComponent(token)}/artifacts/${encodeURIComponent(artifactId)}/thumbnail`;
}

export function publicZipUrl(token: string): string {
  return `${API_BASE}/public/shares/${encodeURIComponent(token)}/zip`;
}
