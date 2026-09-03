import React, { useEffect, useState } from 'react';
import {
  addPlannedTestPipes,
  createPlannedTestList,
  deletePlannedTestBundle,
  deletePlannedTestList,
  deletePlannedTestPipe,
  fetchPlannedTestLists,
  fetchPlannedTestPipes,
  fetchTestByLog,
  updatePlannedTestList,
  updatePlannedTestPipe,
} from '../api';
import { PlannedTestList, PlannedTestListDetail, PlannedTestPipe, PressureTest } from '../types';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { CheckCircle2, ClipboardList, Clock3, Pencil, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';

interface PlannedTestsTabProps {
  onSelectTest: (test: PressureTest) => void;
}

type SortMode = 'bundle' | 'pipe' | 'date' | 'pressure' | 'log';

const compareNatural = (left: string, right: string) => left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });

const pressureValue = (value?: string | null) => {
  const parsed = Number.parseFloat((value || '').replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : -1;
};

export const PlannedTestsTab: React.FC<PlannedTestsTabProps> = ({ onSelectTest }) => {
  const { t } = useI18n();
  const { token } = useAuth();
  const [plans, setPlans] = useState<PlannedTestList[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PlannedTestListDetail | null>(null);
  const [planName, setPlanName] = useState('');
  const [planDescription, setPlanDescription] = useState('');
  const [pipeInput, setPipeInput] = useState('');
  const [search, setSearch] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('bundle');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPlans = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlannedTestLists();
      setPlans(data);
      setSelectedPlanId((current) => current && data.some((plan) => plan.id === current) ? current : data[0]?.id || null);
    } catch (err: any) {
      setError(err.message || t('planned_load_error'));
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (planId: string, query = '') => {
    try {
      setError(null);
      setDetail(await fetchPlannedTestPipes(planId, query));
    } catch (err: any) {
      setError(err.message || t('planned_load_error'));
    }
  };

  useEffect(() => {
    loadPlans();
  }, []);

  useEffect(() => {
    if (!selectedPlanId) {
      setDetail(null);
      return;
    }
    const timer = window.setTimeout(() => loadDetail(selectedPlanId, search), 150);
    return () => window.clearTimeout(timer);
  }, [selectedPlanId, search]);

  const refreshSelectedPlan = async () => {
    await loadPlans();
    if (selectedPlanId) await loadDetail(selectedPlanId, search);
  };

  const handleCreatePlan = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!planName.trim()) return;
    try {
      setSaving(true);
      const created = await createPlannedTestList(planName.trim(), planDescription.trim(), token);
      setPlanName('');
      setPlanDescription('');
      await loadPlans();
      setSelectedPlanId(created.id);
    } catch (err: any) {
      setError(err.message || t('planned_create_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleAddPipes = async () => {
    if (!selectedPlanId || !pipeInput.trim()) return;
    try {
      setSaving(true);
      await addPlannedTestPipes(selectedPlanId, pipeInput, token);
      setPipeInput('');
      await refreshSelectedPlan();
    } catch (err: any) {
      setError(err.message || t('planned_add_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleEditPlan = async () => {
    if (!detail) return;
    const name = window.prompt(t('planned_edit_name'), detail.list.name);
    if (name === null || !name.trim()) return;
    const description = window.prompt(t('planned_edit_description'), detail.list.description || '');
    if (description === null) return;
    try {
      setSaving(true);
      await updatePlannedTestList(detail.list.id, { name: name.trim(), description }, token);
      await refreshSelectedPlan();
    } catch (err: any) {
      setError(err.message || t('planned_update_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePlan = async () => {
    if (!detail || !window.confirm(t('planned_delete_plan_confirm', { plan: detail.list.name }))) return;
    try {
      setSaving(true);
      await deletePlannedTestList(detail.list.id, token);
      setSelectedPlanId(null);
      setDetail(null);
      await loadPlans();
    } catch (err: any) {
      setError(err.message || t('planned_delete_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleEditPipe = async (pipe: PlannedTestPipe, event: React.MouseEvent) => {
    event.stopPropagation();
    const pipeNumber = window.prompt(t('planned_edit_pipe'), pipe.pipe_number);
    if (pipeNumber === null || !pipeNumber.trim()) return;
    try {
      setSaving(true);
      await updatePlannedTestPipe(pipe.id, pipeNumber, token);
      await refreshSelectedPlan();
    } catch (err: any) {
      setError(err.message || t('planned_update_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePipe = async (pipe: PlannedTestPipe, event: React.MouseEvent) => {
    event.stopPropagation();
    if (!window.confirm(t('planned_delete_pipe_confirm', { pipe: pipe.pipe_number }))) return;
    try {
      setSaving(true);
      await deletePlannedTestPipe(pipe.id, token);
      await refreshSelectedPlan();
    } catch (err: any) {
      setError(err.message || t('planned_delete_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteBundle = async (bundleNumber: string, count: number) => {
    if (!selectedPlanId || !window.confirm(t('planned_delete_bundle_confirm', { bundle: bundleNumber, count }))) return;
    try {
      setSaving(true);
      await deletePlannedTestBundle(selectedPlanId, bundleNumber, token);
      await refreshSelectedPlan();
    } catch (err: any) {
      setError(err.message || t('planned_delete_error'));
    } finally {
      setSaving(false);
    }
  };

  const handleOpenLog = async (pipe: PlannedTestPipe) => {
    if (!pipe.matching_logs.length) return;
    let logNo = pipe.matching_logs[0].log_no;
    if (pipe.matching_logs.length > 1) {
      const choices = pipe.matching_logs.map((log) => log.log_no).join(', ');
      const selected = window.prompt(t('planned_choose_log', { logs: choices }), logNo);
      if (!selected) return;
      const match = pipe.matching_logs.find((log) => log.log_no === selected.trim().toUpperCase());
      if (!match) {
        setError(t('planned_log_not_found'));
        return;
      }
      logNo = match.log_no;
    }
    try {
      onSelectTest(await fetchTestByLog(logNo));
    } catch (err: any) {
      setError(err.message || t('planned_log_not_found'));
    }
  };

  const getDisplayRows = () => {
    if (!detail) return [];
    const rows = [...detail.pipes];
    if (sortMode === 'pipe') rows.sort((left, right) => compareNatural(left.pipe_number, right.pipe_number));
    if (sortMode === 'date') rows.sort((left, right) => (right.latest_log_at || '').localeCompare(left.latest_log_at || ''));
    if (sortMode === 'pressure') rows.sort((left, right) => pressureValue(right.latest_test_pressure) - pressureValue(left.latest_test_pressure));
    if (sortMode === 'log') rows.sort((left, right) => compareNatural(left.latest_log_no || '', right.latest_log_no || ''));
    return rows;
  };

  const renderPipe = (pipe: PlannedTestPipe) => {
    const [bundle, suffix = ''] = pipe.pipe_number.split('/', 2);
    const completed = pipe.status === 'completed';
    return (
      <div key={pipe.id} style={{ border: `1px solid ${completed ? 'rgba(16, 185, 129, 0.42)' : 'var(--border-color)'}`, borderRadius: 'var(--radius-sm)', background: completed ? 'rgba(16, 185, 129, 0.09)' : 'var(--bg-inset-40)', opacity: completed ? 1 : 0.84 }}>
        <button
          type="button"
          onClick={() => handleOpenLog(pipe)}
          disabled={!completed}
          title={completed ? t('planned_open_log', { log: pipe.latest_log_no || '' }) : t('planned_pending')}
          style={{ width: '100%', display: 'grid', gridTemplateColumns: 'minmax(150px, 1.25fr) minmax(105px, 0.75fr) minmax(90px, 0.6fr) auto', gap: '0.75rem', alignItems: 'center', padding: '0.7rem 0.8rem', border: 'none', background: 'transparent', color: 'var(--text-primary)', cursor: completed ? 'pointer' : 'default', textAlign: 'left' }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
            {completed ? <CheckCircle2 size={17} color="var(--accent-emerald)" /> : <Clock3 size={17} color="var(--text-muted)" />}
            <span className="log-number" style={{ fontSize: '0.94rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <span style={{ color: 'var(--text-secondary)' }}>{bundle}</span><span style={{ color: 'var(--accent-cyan)' }}>/{suffix}</span>
            </span>
          </span>
          <span style={{ fontSize: '0.78rem', color: completed ? 'var(--accent-emerald)' : 'var(--text-muted)', fontWeight: 700 }}>{completed ? t('planned_completed') : t('planned_pending')}</span>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{completed ? `${pipe.latest_log_no} ${pipe.latest_test_pressure ? `· ${pipe.latest_test_pressure}` : ''}` : '—'}</span>
          <span style={{ display: 'flex', gap: '0.2rem', justifyContent: 'flex-end' }}>
            <span role="button" tabIndex={0} onClick={(event) => handleEditPipe(pipe, event as unknown as React.MouseEvent)} title={t('planned_edit_pipe')} style={{ color: 'var(--text-muted)', padding: '0.35rem', display: 'inline-flex' }}><Pencil size={15} /></span>
            <span role="button" tabIndex={0} onClick={(event) => handleDeletePipe(pipe, event as unknown as React.MouseEvent)} title={t('planned_delete_pipe')} style={{ color: 'var(--accent-rose)', padding: '0.35rem', display: 'inline-flex' }}><Trash2 size={15} /></span>
          </span>
        </button>
        {pipe.source_data?.raw_source && <details style={{ borderTop: '1px solid var(--border-color)', padding: '0.45rem 0.8rem' }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontSize: '0.78rem' }}>{t('planned_source_columns')}</summary>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.45rem', marginTop: '0.6rem' }}>
            {['product', 'drawing', 'spool_number', 'order_number', 'revision', 'pipeline', 'pt', 'wp', 'kg', 'class', 'treatment', 'size', 'wt', 'material', 'bundles', 'pdd_start', 'pdd_end', 'status'].map((field) => <div key={field} style={{ minWidth: 0 }}><div style={{ color: 'var(--text-muted)', fontSize: '0.65rem', textTransform: 'uppercase' }}>{field.replace(/_/g, ' ')}</div><div style={{ color: 'var(--text-primary)', fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{pipe.source_data[field] || '—'}</div></div>)}
          </div>
          <div style={{ marginTop: '0.6rem', color: 'var(--text-muted)', fontSize: '0.7rem' }}>{t('planned_source_raw')}</div>
          <div style={{ marginTop: '0.15rem', overflowWrap: 'anywhere', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', lineHeight: 1.35 }}>{pipe.source_data.raw_source}</div>
        </details>}
      </div>
    );
  };

  const displayRows = getDisplayRows();

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(230px, 0.42fr) minmax(0, 1.58fr)', gap: '1.25rem', alignItems: 'start' }}>
      <aside style={{ border: '1px solid var(--border-color)', background: 'var(--bg-surface)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem' }}>
          <ClipboardList size={19} color="var(--accent-cyan)" />
          <strong>{t('planned_lists_title')}</strong>
        </div>
        <form onSubmit={handleCreatePlan} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
          <input className="search-input" style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.55rem 0.65rem', background: 'var(--bg-inset-40)' }} placeholder={t('planned_name_placeholder')} value={planName} onChange={(event) => setPlanName(event.target.value)} />
          <input className="search-input" style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.55rem 0.65rem', background: 'var(--bg-inset-40)' }} placeholder={t('planned_description_placeholder')} value={planDescription} onChange={(event) => setPlanDescription(event.target.value)} />
          <button type="submit" className="btn-primary" disabled={saving || !planName.trim()} style={{ justifyContent: 'center', padding: '0.5rem 0.75rem', fontSize: '0.85rem' }}><Plus size={16} /><span>{t('planned_create')}</span></button>
        </form>
        {loading ? <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{t('planned_loading')}</div> : plans.length === 0 ? <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', lineHeight: 1.5 }}>{t('planned_empty_lists')}</div> : <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {plans.map((plan) => {
            const active = plan.id === selectedPlanId;
            return <button key={plan.id} type="button" onClick={() => setSelectedPlanId(plan.id)} style={{ textAlign: 'left', padding: '0.65rem', borderRadius: 'var(--radius-sm)', border: active ? '1px solid var(--accent-cyan)' : '1px solid transparent', background: active ? 'rgba(56, 189, 248, 0.1)' : 'transparent', color: 'var(--text-primary)', cursor: 'pointer' }}>
              <div style={{ fontWeight: 700, fontSize: '0.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plan.name}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.15rem' }}>{plan.completed_count}/{plan.pipe_count} {t('planned_ready_count')}</div>
            </button>;
          })}
        </div>}
      </aside>

      <section style={{ minWidth: 0 }}>
        {error && <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', color: 'var(--error-text)', border: '1px solid var(--accent-rose)', borderRadius: 'var(--radius-sm)', background: 'rgba(244, 63, 94, 0.1)' }}>{error}</div>}
        {!selectedPlanId || !detail ? <div className="empty-state"><ClipboardList size={48} style={{ opacity: 0.4, marginBottom: '1rem' }} /><div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{t('planned_empty_title')}</div><p>{t('planned_empty_desc')}</p></div> : <>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.2rem', marginBottom: '0.2rem' }}>{detail.list.name}</h2>
              {detail.list.description && <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{detail.list.description}</div>}
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.45rem' }}>{detail.summary.completed}/{detail.summary.total} {t('planned_ready_count')}</div>
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button type="button" className="filter-pill" onClick={handleEditPlan} title={t('planned_edit_name')}><Pencil size={15} /></button>
              <button type="button" className="filter-pill" onClick={handleDeletePlan} title={t('planned_delete_plan')} style={{ color: 'var(--accent-rose)' }}><Trash2 size={15} /></button>
              <button type="button" className="filter-pill" onClick={() => loadDetail(detail.list.id, search)} title={t('btn_refresh')}><RefreshCw size={15} /></button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="search-input-wrapper"><Search size={17} className="search-icon" /><input className="search-input" placeholder={t('planned_search_placeholder')} value={search} onChange={(event) => setSearch(event.target.value)} /></div>
            <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} aria-label={t('planned_sort')} style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0 0.65rem', fontSize: '0.85rem' }}>
              <option value="bundle">{t('planned_sort_bundle')}</option><option value="pipe">{t('planned_sort_pipe')}</option><option value="date">{t('planned_sort_date')}</option><option value="pressure">{t('planned_sort_pressure')}</option><option value="log">{t('planned_sort_log')}</option>
            </select>
          </div>

          <div style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.85rem', background: 'var(--bg-inset-40)', marginBottom: '1.15rem' }}>
            <label style={{ display: 'block', fontWeight: 700, fontSize: '0.85rem', marginBottom: '0.45rem' }}>{t('planned_add_pipes')}</label>
            <textarea value={pipeInput} onChange={(event) => setPipeInput(event.target.value)} placeholder={t('planned_pipe_input_placeholder')} rows={4} style={{ width: '100%', resize: 'vertical', border: '1px solid var(--border-color)', background: 'var(--bg-surface)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', fontFamily: 'var(--font-mono)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'center', marginTop: '0.55rem', flexWrap: 'wrap' }}><span style={{ color: 'var(--text-muted)', fontSize: '0.76rem' }}>{t('planned_input_hint')}</span><button type="button" className="btn-primary" onClick={handleAddPipes} disabled={saving || !pipeInput.trim()} style={{ padding: '0.45rem 0.85rem', fontSize: '0.85rem' }}><Plus size={15} /><span>{t('planned_add')}</span></button></div>
          </div>

          {displayRows.length === 0 ? <div className="empty-state" style={{ padding: '2.5rem 1rem' }}>{t('planned_no_pipes')}</div> : sortMode === 'bundle' ? detail.bundles.map((bundle) => <div key={bundle.bundle_number} style={{ marginBottom: '1rem', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}>
            <div style={{ padding: '0.65rem 0.85rem', background: 'var(--bg-inset-60)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'center' }}><div><strong style={{ color: 'var(--text-secondary)' }}>{t('planned_bundle')} {bundle.bundle_number}</strong><span style={{ marginLeft: '0.55rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>{bundle.completed_count}/{bundle.pipes.length} {t('planned_ready_count')}</span></div><button type="button" className="filter-pill" onClick={() => handleDeleteBundle(bundle.bundle_number, bundle.pipes.length)} title={t('planned_delete_bundle')} style={{ color: 'var(--accent-rose)', padding: '0.3rem' }}><Trash2 size={14} /></button></div>
            <div style={{ padding: '0.45rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>{bundle.pipes.map(renderPipe)}</div>
          </div>) : <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>{displayRows.map(renderPipe)}</div>}
        </>}
      </section>
    </div>
  );
};
