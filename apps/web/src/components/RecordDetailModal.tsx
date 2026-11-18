import React, { useEffect, useRef, useState } from 'react';
import { PressureTestRecord, RecordLog } from '../types';
import { getRecordPdfUrl, getRecordFullPdfUrl, deleteRecord, previewRecordPdf, updateRecord, unconfirmRecord } from '../api';
import {
  X,
  Download,
  ShieldCheck,
  Edit,
  ExternalLink,
  Eye,
  Table,
  FileSpreadsheet,
  Trash2,
  Layers,
  Check,
  Plus
} from 'lucide-react';
import { SignatureModal } from './SignatureModal';
import { ConfirmRecordModal } from './ConfirmRecordModal';
import { useI18n } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

type AttachmentOverrides = {
  ins_no?: string;
  system?: string;
  project?: string;
  operator?: string;
  test_pressure?: string;
  wika_nr?: string;
  evaluation_status?: string;
  note?: string;
};

const ATTACHMENT_TEXT_FIELDS: ReadonlyArray<readonly [keyof AttachmentOverrides, string]> = [
  ['ins_no', 'Inspection No'],
  ['system', 'System'],
  ['project', 'Project'],
  ['operator', 'Operator / Tester'],
  ['test_pressure', 'Target pressure'],
  ['wika_nr', 'WIKA S#'],
];

const inputStyle: React.CSSProperties = { background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)', padding: '0.45rem 0.55rem' };

const logLabel = (log: RecordLog, index: number): string => {
  const raw = String(log.log_no || log.metadata_snapshot?.metadata?.log_no || '').trim();
  const bare = raw.replace(/^log[\s_#-]*/i, '').trim();
  return `Log ${bare || `#${index + 1}`}`;
};

const overridesFromRecord = (record: PressureTestRecord): Record<string, AttachmentOverrides> =>
  Object.fromEntries(
    (record.logs || [])
      .filter((log) => log.id)
      .map((log) => [log.id as string, { ...(log.metadata_snapshot?.attachment_overrides || {}) }]),
  );

type RecordDraft = {
  project: string;
  system: string;
  ins_no: string;
  test_medium: string;
  design_pressure: string;
  test_pressure: string;
  duration_min: string;
  foreman_name: string;
  notes: string;
};

const draftFromRecord = (record: PressureTestRecord): RecordDraft => ({
  project: record.project,
  system: record.system,
  ins_no: record.ins_no || '',
  test_medium: record.test_medium,
  design_pressure: record.design_pressure || '',
  test_pressure: record.test_pressure || '',
  duration_min: record.duration_min,
  foreman_name: record.foreman_name || '',
  notes: record.notes || '',
});

/** Body of PUT /records/{id} and of the live preview: same values, so the preview shows what Save would store. */
const buildRecordPayload = (
  record: PressureTestRecord,
  draft: RecordDraft,
  logOverrides: Record<string, AttachmentOverrides>,
): Record<string, unknown> => {
  const payload: Record<string, unknown> = { ...draft, items: record.items };
  if ((record.logs || []).some((log) => log.id)) payload.log_overrides = logOverrides;
  return payload;
};

// Phones do not show the embedded PDF at all (see .pdf-frame), so no live preview there.
const isPhoneLayout = () => typeof window !== 'undefined' && window.matchMedia?.('(max-width: 900px)').matches;

interface RecordDetailModalProps {
  record: PressureTestRecord;
  onClose: () => void;
  onUpdate: () => void;
}

export const RecordDetailModal: React.FC<RecordDetailModalProps> = ({
  record: initialRecord,
  onClose,
  onUpdate
}) => {
  const { t } = useI18n();
  const { user } = useAuth();
  // Guests and viewers only read and download; mutations are for admin/foreman (ADR-005).
  const canEdit = user?.role === 'admin' || user?.role === 'foreman';
  const [record, setRecord] = useState<PressureTestRecord>(initialRecord);
  const [activeView, setActiveView] = useState<'official_pdf' | 'full_pdf' | 'data'>('official_pdf');
  const [isSignOpen, setIsSignOpen] = useState<boolean>(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draft, setDraft] = useState<RecordDraft>(() => draftFromRecord(initialRecord));
  const [logOverrides, setLogOverrides] = useState<Record<string, AttachmentOverrides>>(() => overridesFromRecord(initialRecord));
  // Bumped after every save so the embedded PDF is re-rendered with the new values.
  const [pdfVersion, setPdfVersion] = useState<number>(0);

  // Live preview of the unsaved form (PDF next to the editor).
  const [preview, setPreview] = useState<{ url: string; logPages: Record<string, number> } | null>(null);
  const [previewState, setPreviewState] = useState<'idle' | 'loading' | 'error'>('idle');
  const [previewError, setPreviewError] = useState('');
  const [focusTarget, setFocusTarget] = useState<string>('record');
  const [savedPayloadJson, setSavedPayloadJson] = useState('');
  const previewUrlRef = useRef<string | null>(null);

  const startEditing = () => {
    const nextDraft = draftFromRecord(record);
    const nextOverrides = overridesFromRecord(record);
    setDraft(nextDraft);
    setSavedPayloadJson(JSON.stringify(buildRecordPayload(record, nextDraft, nextOverrides)));
    setFocusTarget('record');
    setLogOverrides(overridesFromRecord(record));
    // The full PDF contains page 1 and the log attachments: show it next to the form.
    if (activeView === 'official_pdf') setActiveView('full_pdf');
    setIsEditing(true);
  };

  const updateLogOverride = (logId: string, field: keyof AttachmentOverrides, value: string) => {
    setLogOverrides((current) => ({ ...current, [logId]: { ...(current[logId] || {}), [field]: value } }));
  };

  const handleDeleteRecord = async () => {
    const confirmed = window.confirm(t('delete_record_confirm', { record: record.record_number }));
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      await deleteRecord(record.id);
      onUpdate();
      onClose();
    } catch (err: any) {
      alert(err.message || 'Failed to delete record');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const updated = await updateRecord(record.id, buildRecordPayload(record, draft, logOverrides));
      const savedOverrides = overridesFromRecord(updated);
      setRecord(updated);
      setLogOverrides(savedOverrides);
      setSavedPayloadJson(JSON.stringify(buildRecordPayload(updated, draft, savedOverrides)));
      // The editor stays open: the PDF next to it is re-rendered, the next correction can follow.
      setPdfVersion((value) => value + 1);
      onUpdate();
    } catch (err: any) {
      alert(err.message || 'Не удалось сохранить изменения');
    } finally {
      setIsSaving(false);
    }
  };

  const handleUnconfirm = async () => {
    if (!window.confirm('Снять подтверждение? Текущий штамп и код будут отозваны, а рапорт вернётся в черновик.')) return;
    try {
      setIsSaving(true);
      const updated = await unconfirmRecord(record.id);
      setRecord(updated);
      onUpdate();
    } catch (err: any) {
      alert(err.message || 'Не удалось снять подтверждение');
    } finally {
      setIsSaving(false);
    }
  };

  const updateItem = (index: number, field: string, value: string) => {
    setRecord((current) => ({ ...current, items: current.items.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) }));
  };

  const addItem = () => {
    setRecord((current) => ({ ...current, items: [...current.items, { item_no: current.items.length + 1, pipe_number: '', drawing_no: '', spool_no: '', log_no: '', hold_start_bar: '', hold_end_bar: '', result: 'PENDING', notes: '' }] }));
  };

  const removeItem = (index: number) => {
    setRecord((current) => ({ ...current, items: current.items.filter((_, itemIndex) => itemIndex !== index).map((item, itemIndex) => ({ ...item, item_no: itemIndex + 1 })) }));
  };

  const handleSignatureSuccess = (updated: PressureTestRecord) => {
    setRecord(updated);
    setIsSignOpen(false);
    onUpdate();
  };

  const handleConfirmSuccess = (updated: PressureTestRecord) => {
    setRecord(updated);
    setIsConfirmOpen(false);
    onUpdate();
  };

  const splitView = isEditing && activeView !== 'data';
  const previewKind: 'full' | 'official' = activeView === 'official_pdf' ? 'official' : 'full';
  const payloadJson = splitView ? JSON.stringify(buildRecordPayload(record, draft, logOverrides)) : '';
  const isDirty = isEditing && Boolean(savedPayloadJson) && payloadJson !== '' && payloadJson !== savedPayloadJson;

  const replacePreview = (next: { url: string; logPages: Record<string, number> } | null) => {
    const old = previewUrlRef.current;
    previewUrlRef.current = next?.url || null;
    // The old iframe may still be reading the previous blob for a moment.
    if (old) window.setTimeout(() => URL.revokeObjectURL(old), 10000);
    setPreview(next);
  };

  // Every change of the form re-renders the PDF (debounced); nothing is saved until "Save".
  useEffect(() => {
    if (!splitView || isPhoneLayout()) {
      if (previewUrlRef.current) replacePreview(null);
      setPreviewState('idle');
      return undefined;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setPreviewState('loading');
      try {
        const { blob, logPages } = await previewRecordPdf(record.id, previewKind, JSON.parse(payloadJson), controller.signal);
        if (controller.signal.aborted) return;
        replacePreview({ url: URL.createObjectURL(new Blob([blob], { type: 'application/pdf' })), logPages });
        setPreviewState('idle');
      } catch (err: any) {
        if (controller.signal.aborted) return;
        setPreviewError(err?.message || 'Preview failed');
        setPreviewState('error');
      }
    }, previewUrlRef.current ? 700 : 0);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [splitView, previewKind, payloadJson, record.id]);

  useEffect(() => () => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
  }, []);

  // Open the page that is being edited: page 1 for the blank, the log's attachment page for a log.
  const previewPage = focusTarget === 'record' ? 1 : (preview?.logPages[focusTarget] || 1);
  const pdfQuery = pdfVersion ? `?v=${pdfVersion}` : '';
  const officialPdfUrl = `${getRecordPdfUrl(record.id)}${pdfQuery}`;
  const fullPdfUrl = `${getRecordFullPdfUrl(record.id)}${pdfQuery}`;
  const currentActivePdfUrl = activeView === 'full_pdf' ? fullPdfUrl : officialPdfUrl;
  const showPreview = splitView && preview !== null;
  const iframeSrc = showPreview && preview
    ? `${preview.url}#page=${previewPage}&toolbar=1&navpanes=0`
    : `${currentActivePdfUrl}#toolbar=1&navpanes=0`;
  const iframeKey = showPreview && preview ? `${preview.url}-${previewPage}` : `${activeView}-${pdfVersion}`;
  const subtitle = [record.ins_no, record.system, record.project].filter((part) => part && String(part).trim()).join(' — ');
  // confirmed_by_name may already contain the role, e.g. "Matti Meikäläinen (Foreman)".
  const signerRole = record.confirmed_by_role || '';
  const showSignerRole = Boolean(signerRole) && !(record.confirmed_by_name || '').toLowerCase().includes(`(${signerRole.toLowerCase()})`);

  return (
    <>
      <div className="modal-overlay">
        <div className="modal-content" style={{ maxWidth: splitView ? '1640px' : '1020px', width: '96vw' }} onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          {/* Header */}
          <div className="modal-header record-detail-header">
            <div className="test-detail-header-top">
              <div className="test-detail-title-group">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <FileSpreadsheet size={22} color="var(--accent-amber)" />
                  <span className="log-number" style={{ color: 'var(--accent-amber)', fontSize: '1.3rem' }}>
                    {record.record_number}
                  </span>
                  <span className={`status-badge ${record.status}`}>
                    {record.status}
                  </span>
                </div>
                {subtitle && (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.2rem', overflowWrap: 'anywhere' }}>
                    {subtitle}
                  </div>
                )}
              </div>

              <button className="modal-close-btn" onClick={onClose} title={t('modal_close')} aria-label={t('modal_close')}>
                <X size={20} />
              </button>
            </div>

            <div className="test-detail-actions">
              {canEdit && (record.status === 'confirmed' || record.status === 'signed') && (
                <button
                  type="button"
                  onClick={() => void handleUnconfirm()}
                  disabled={isSaving}
                  className="filter-pill"
                  style={{ background: 'rgba(245, 158, 11, 0.14)', color: 'var(--accent-amber)', border: '1px solid var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', cursor: 'pointer' }}
                  title={t('ptr_unconfirm_hint')}
                >
                  <Edit size={14} />
                  <span>{t('ptr_unconfirm')}</span>
                </button>
              )}
              {canEdit && record.status !== 'confirmed' && record.status !== 'signed' && (
                <button
                  type="button"
                  onClick={() => (isEditing ? setIsEditing(false) : startEditing())}
                  className="filter-pill"
                  style={{ background: isEditing ? 'rgba(245, 158, 11, 0.14)' : 'rgba(56, 189, 248, 0.12)', color: isEditing ? 'var(--accent-amber)' : 'var(--accent-cyan)', border: `1px solid ${isEditing ? 'var(--accent-amber)' : 'var(--accent-cyan)'}`, display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', cursor: 'pointer' }}
                  title={t('ptr_edit')}
                >
                  <Edit size={14} />
                  <span>{isEditing ? t('ptr_cancel') : t('ptr_edit')}</span>
                </button>
              )}
              {isEditing && (
                <button type="button" onClick={() => void handleSave()} disabled={isSaving} className="btn-primary" style={{ padding: '0.45rem 0.8rem', fontSize: '0.85rem' }}>
                  <Check size={14} />
                  <span>{isSaving ? t('ptr_saving') : t('ptr_save')}</span>
                </button>
              )}
              {canEdit && <button
                type="button"
                onClick={handleDeleteRecord}
                disabled={isDeleting}
                className="filter-pill"
                style={{ background: 'rgba(244, 63, 94, 0.12)', color: 'var(--accent-rose)', border: '1px solid var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', cursor: 'pointer' }}
                title={t('btn_delete_record')}
              >
                <Trash2 size={14} />
                <span>{isDeleting ? t('modal_saving') : t('btn_delete')}</span>
              </button>}

              <a
                href={currentActivePdfUrl}
                target="_blank"
                rel="noreferrer"
                className="filter-pill"
                style={{ background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', textDecoration: 'none' }}
                title={t('btn_open_new_tab')}
              >
                <ExternalLink size={14} />
                <span>{t('btn_open_new_tab')}</span>
              </a>

              <a
                href={officialPdfUrl}
                className="btn-primary"
                download={`PTR_${record.record_number}_Official.pdf`}
                style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                title="Download Official Blank PDF"
              >
                <Download size={15} />
                <span>{t('btn_download_pdf')}</span>
              </a>

              <a
                href={fullPdfUrl}
                className="btn-primary"
                download={`PTR_${record.record_number}_Full.pdf`}
                style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem', background: 'linear-gradient(135deg, #10b981, #059669)' }}
                title="Download Complete Composite PDF (All Logs & Measurement Tables)"
              >
                <Layers size={15} />
                <span>{t('btn_download_full_pdf')}</span>
              </a>
            </div>
          </div>

          {/* View Mode Toggle & Actions Bar */}
          <div className="record-view-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                className={`filter-pill ${activeView === 'official_pdf' ? 'active' : ''}`}
                onClick={() => setActiveView('official_pdf')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
              >
                <Eye size={15} />
                <span>{t('view_pdf_tab')}</span>
              </button>

              <button
                type="button"
                className={`filter-pill ${activeView === 'full_pdf' ? 'active' : ''}`}
                onClick={() => setActiveView('full_pdf')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', borderColor: activeView === 'full_pdf' ? 'var(--accent-emerald)' : undefined }}
              >
                <Layers size={15} color="var(--accent-emerald)" />
                <span>{t('view_full_pdf_tab')}</span>
              </button>

              <button
                type="button"
                className={`filter-pill ${activeView === 'data' ? 'active' : ''}`}
                onClick={() => setActiveView('data')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
              >
                <Table size={15} />
                <span>{t('view_data_tab')} ({record.items?.length || 0})</span>
              </button>
            </div>

            {/* Workflow Action Buttons */}
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {canEdit && record.status === 'draft' && (
                <>
                  <button
                    type="button"
                    className="filter-pill"
                    style={{ background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)', border: '1px solid var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.85rem' }}
                    onClick={() => setIsSignOpen(true)}
                  >
                    <Edit size={14} />
                    <span>{t('btn_draw_signature')}</span>
                  </button>

                  <button
                    type="button"
                    className="btn-primary"
                    style={{ background: 'var(--accent-emerald)', padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                    onClick={() => setIsConfirmOpen(true)}
                  >
                    <ShieldCheck size={15} />
                    <span>{t('btn_seal_record')}</span>
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Body */}
          <div className="modal-body" style={{ gap: '1.25rem' }}>
            {/* Digital Verification Seal Card if Confirmed */}
            {record.verification_code && (
              <div className="record-seal" style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', minWidth: 0, flex: '1 1 260px' }}>
                  <div style={{ width: '38px', height: '38px', flexShrink: 0, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <ShieldCheck size={22} color="var(--accent-emerald)" />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.25rem 0.5rem' }}>
                      <span>{t('verified_badge')}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', background: 'rgba(16, 185, 129, 0.2)', padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-sm)', overflowWrap: 'anywhere' }}>
                        {record.verification_code}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem', overflowWrap: 'anywhere' }}>
                      {t('signed_by')}: <strong>{record.confirmed_by_name}</strong>{showSignerRole ? ` (${signerRole})` : ''}
                    </div>
                    {record.official_pdf_sha256 && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.15rem', overflowWrap: 'anywhere' }}>
                        Official PDF SHA-256: {record.official_pdf_sha256}
                      </div>
                    )}
                    {record.full_pdf_sha256 && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.1rem', overflowWrap: 'anywhere' }}>
                        Full PDF SHA-256: {record.full_pdf_sha256}
                      </div>
                    )}
                  </div>
                </div>

                <span className="status-badge complete" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}>
                  IMMUTABLE OFFICIAL BLANK
                </span>
              </div>
            )}

            <div className={`ptr-edit-layout${splitView ? ' is-split' : ''}`}>
            {/* EDIT PANEL: on the PDF tabs it sits next to the PDF, which is re-rendered after each save */}
            {isEditing && (
              <div className="ptr-edit-panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', padding: '0.9rem', border: '1px solid var(--accent-cyan)', borderRadius: 'var(--radius-md)', background: 'rgba(56, 189, 248, 0.06)' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Бланк протокола (страница 1)
                </div>
                <div onFocusCapture={() => setFocusTarget('record')} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                  {([
                    ['project', 'Проект'], ['system', 'Система'], ['ins_no', 'Inspection No'], ['test_medium', 'Среда'],
                    ['design_pressure', 'Design pressure'], ['test_pressure', 'Test pressure'], ['duration_min', 'Длительность'], ['foreman_name', 'Прораб'],
                  ] as const).map(([field, label]) => (
                    <label key={field} style={{ display: 'grid', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {label}
                      <input value={draft[field]} onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.value }))} style={inputStyle} />
                    </label>
                  ))}
                  <label style={{ display: 'grid', gap: '0.25rem', gridColumn: '1 / -1', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Примечания
                    <textarea value={draft.notes} onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))} rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
                  </label>
                </div>

                {(record.logs || []).filter((log) => log.id).map((log, logIndex) => {
                  const logId = log.id as string;
                  const values = logOverrides[logId] || {};
                  const source = (log.metadata_snapshot?.metadata || {}) as Record<string, any>;
                  return (
                    <div key={logId} onFocusCapture={() => setFocusTarget(logId)} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.8rem' }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Приложение: {logLabel(log, logIndex)}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Пустое поле = значение из самого лога (показано серым). Изменения действуют только в этом протоколе.
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                        {ATTACHMENT_TEXT_FIELDS.map(([field, label]) => (
                          <label key={field} style={{ display: 'grid', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {label}
                            <input
                              value={values[field] || ''}
                              placeholder={String((field === 'ins_no' ? (draft.ins_no || source.ins_no) : field === 'operator' ? (source.operator || log.metadata_snapshot?.operator) : source[field]) || '—')}
                              onChange={(event) => updateLogOverride(logId, field, event.target.value)}
                              style={inputStyle}
                            />
                          </label>
                        ))}
                        <label style={{ display: 'grid', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Evaluation Status
                          <select value={values.evaluation_status || ''} onChange={(event) => updateLogOverride(logId, 'evaluation_status', event.target.value)} style={inputStyle}>
                            <option value="">Авто (по результатам строк протокола)</option>
                            <option value="PASS">PASS</option>
                            <option value="FAIL">FAIL</option>
                            <option value="NOT EVALUATED">NOT EVALUATED</option>
                          </select>
                        </label>
                        <label style={{ display: 'grid', gap: '0.25rem', gridColumn: '1 / -1', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Log Notes &amp; Observations
                          <textarea
                            value={values.note || ''}
                            placeholder={String(source.note || '—')}
                            onChange={(event) => updateLogOverride(logId, 'note', event.target.value)}
                            rows={2}
                            style={{ ...inputStyle, resize: 'vertical' }}
                          />
                        </label>
                      </div>
                    </div>
                  );
                })}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => setIsEditing(false)} className="filter-pill" style={{ padding: '0.45rem 0.9rem', cursor: 'pointer' }}>
                    {t('ptr_close_editor')}
                  </button>
                  <button type="button" onClick={() => void handleSave()} disabled={isSaving} className="btn-primary" style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}>
                    <Check size={14} />
                    <span>{isSaving ? t('ptr_saving') : t('ptr_save')}</span>
                  </button>
                </div>
              </div>
            )}

            {/* TAB 1 & 2: LIVE PDF VIEWER (Official or Full) */}
            {(activeView === 'official_pdf' || activeView === 'full_pdf') ? (
              <div className="ptr-pdf-pane" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {/* Phones cannot render a PDF inside an iframe (Android shows nothing, iOS only page 1). */}
                <div className="pdf-mobile-fallback">
                  <FileSpreadsheet size={30} color="var(--accent-amber)" />
                  <strong>{t('pdf_mobile_title')}</strong>
                  <span>{t('pdf_mobile_hint')}</span>
                  <div className="pdf-mobile-actions">
                    <a href={currentActivePdfUrl} target="_blank" rel="noreferrer" className="btn-primary">
                      <ExternalLink size={16} />
                      <span>{t('pdf_open')}</span>
                    </a>
                    <a href={currentActivePdfUrl} download={`PTR_${record.record_number}_${activeView === 'full_pdf' ? 'Full' : 'Official'}.pdf`} className="filter-pill">
                      <Download size={16} />
                      <span>{t('file_download')}</span>
                    </a>
                  </div>
                </div>
                {splitView && (
                  <div className="pdf-frame-caption ptr-preview-status" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <span>{t('ptr_live_preview_hint')}{previewKind === 'full' ? ` ${t('ptr_live_preview_no_tables')}` : ''}</span>
                    <span style={{ fontWeight: 700, color: previewState === 'error' ? 'var(--accent-rose)' : isDirty ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                      {previewState === 'loading' ? t('ptr_live_preview_updating') : previewState === 'error' ? `${t('ptr_live_preview_error')}: ${previewError}` : isDirty ? t('ptr_live_preview_unsaved') : t('ptr_live_preview_saved')}
                    </span>
                  </div>
                )}
                <div className="pdf-frame" style={{ width: '100%', height: '620px', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#fff' }}>
                  <iframe
                    key={iframeKey}
                    src={iframeSrc}
                    title={`ARDOR Pressure Test Record ${activeView === 'full_pdf' ? 'Full Composite' : 'Official'}`}
                    style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
                  />
                </div>
                <div className="pdf-frame-caption" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <span>
                    {activeView === 'full_pdf' ? 'Rendering Full Composite PDF (Record + All Log Sections + Full CSV Tables)' : 'Rendering Official ARDOR Blank (Official Multi-page compliant layout)'}
                  </span>
                  <span>ARDOR Quality & Inspection Procedures</span>
                </div>
              </div>
            ) : (
              /* TAB 3: DATA & PIPES TABLE */
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Meta Summary Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>KOEPAINE / TEST PRESSURE</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {record.test_pressure || '—'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SUUNNITTELUPAINE / DESIGN P.</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.15rem', fontWeight: 700 }}>
                      {record.design_pressure || '—'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TESTIAINE / MEDIUM</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                      {record.test_medium || 'Water'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>KESTO / DURATION</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {record.duration_min || '60 min'}
                    </div>
                  </div>
                </div>

                {/* Pipes Table */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                      Included Pipes & Results ({record.items?.length || 0} lines)
                    </h3>
                      {isEditing && <button type="button" onClick={addItem} className="filter-pill" style={{ color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)', background: 'transparent', padding: '0.35rem 0.65rem', cursor: 'pointer' }}><Plus size={14} /> Добавить строку</button>}
                  </div>

                  <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                        <thead>
                          <tr style={{ background: 'var(--bg-inset-60)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                            <th style={{ padding: '0.65rem 0.85rem' }}>#</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>Drawing No</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>Pipe No</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>Log No</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>Start Bar</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>End Bar</th>
                            <th style={{ padding: '0.65rem 0.85rem' }}>Result</th>
                          </tr>
                        </thead>
                        <tbody>
                            {(record.items || []).map((it, itemIndex) => (
                            <tr key={it.id || it.item_no} style={{ borderBottom: '1px solid var(--border-color)' }}>
                              <td style={{ padding: '0.65rem 0.85rem', color: 'var(--text-muted)' }}>{it.item_no}</td>
                                <td style={{ padding: '0.65rem 0.85rem' }}>{isEditing ? <input value={it.drawing_no || ''} onChange={(event) => updateItem(itemIndex, 'drawing_no', event.target.value)} /> : (it.drawing_no || it.spool_no || '—')}</td>
                                <td style={{ padding: '0.65rem 0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{isEditing ? <input value={it.pipe_number} onChange={(event) => updateItem(itemIndex, 'pipe_number', event.target.value)} /> : it.pipe_number}</td>
                                <td style={{ padding: '0.65rem 0.85rem' }}>{it.log_no ? `Log ${it.log_no}` : '—'}</td>
                                <td style={{ padding: '0.65rem 0.85rem', fontFamily: 'var(--font-mono)' }}>{isEditing ? <input value={it.hold_start_bar || ''} onChange={(event) => updateItem(itemIndex, 'hold_start_bar', event.target.value)} /> : (it.hold_start_bar || '—')}</td>
                                <td style={{ padding: '0.65rem 0.85rem', fontFamily: 'var(--font-mono)' }}>{isEditing ? <input value={it.hold_end_bar || ''} onChange={(event) => updateItem(itemIndex, 'hold_end_bar', event.target.value)} /> : (it.hold_end_bar || '—')}</td>
                              <td style={{ padding: '0.65rem 0.85rem' }}>
                                {isEditing ? (
                                  <select value={it.result || 'PENDING'} onChange={(event) => updateItem(itemIndex, 'result', event.target.value)}>
                                    <option value="PASS">PASS</option>
                                    <option value="FAIL">FAIL</option>
                                    <option value="PENDING">PENDING</option>
                                  </select>
                                ) : (
                                  <span className={`status-badge ${it.result === 'PASS' ? 'complete' : 'pending'}`} style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}>
                                    {it.result}
                                  </span>
                                )}
                              </td>
                                {isEditing && <td><button type="button" onClick={() => removeItem(itemIndex)} title="Удалить строку" style={{ color: 'var(--accent-rose)', background: 'transparent', border: 'none', cursor: 'pointer' }}><Trash2 size={15} /></button></td>}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}
            </div>
          </div>
        </div>
      </div>

      {/* Signature Modal */}
      {isSignOpen && (
        <SignatureModal
          record={record}
          onClose={() => setIsSignOpen(false)}
          onSuccess={handleSignatureSuccess}
        />
      )}

      {/* Confirmation Modal */}
      {isConfirmOpen && (
        <ConfirmRecordModal
          record={record}
          onClose={() => setIsConfirmOpen(false)}
          onSuccess={handleConfirmSuccess}
        />
      )}
    </>
  );
};
