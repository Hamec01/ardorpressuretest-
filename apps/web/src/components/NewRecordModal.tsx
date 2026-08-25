import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  FileSpreadsheet,
  Search,
  Layers,
  Image as ImageIcon,
  Table,
  ArrowUp,
  ArrowDown,
  Camera,
  FileText
} from 'lucide-react';
import { PressureTest, PressureTestRecord, RecordItem, RecordLog, RecordLogArtifact, TestRevision } from '../types';
import { fetchPressureTests, getArtifactFileUrl } from '../api';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';

interface NewRecordModalProps {
  onClose: () => void;
  onSuccess: (created: PressureTestRecord) => void;
}

export const NewRecordModal: React.FC<NewRecordModalProps> = ({ onClose, onSuccess }) => {
  const { token } = useAuth();
  const { t } = useI18n();

  // Document Fields matching official ARDOR PAINEKOEPÖYTÄKIRJA
  const [recordNumber, setRecordNumber] = useState<string>(`PTR-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 9000) + 1000)}`);
  const [insNo, setInsNo] = useState<string>('Inspection 044');
  const [jobNo, setJobNo] = useState<string>('Fuel Gas System');
  const [project, setProject] = useState<string>('ARDOR Project');
  const [designPressure, setDesignPressure] = useState<string>('16 bar');
  const [testPressure, setTestPressure] = useState<string>('24 bar');
  const [testMedium, setTestMedium] = useState<string>('Water');
  const [durationMin] = useState<string>('60 min');
  const [foremanName, setForemanName] = useState<string>('Foreman');
  const [notes, setNotes] = useState<string>('Hold test completed according to ARDOR quality procedures. No pressure drop detected.');

  // Attached Logs (Composite PTR logs)
  const [attachedLogs, setAttachedLogs] = useState<RecordLog[]>([]);
  
  // Table rows matching Drawing No, System, Part No, Date, Duration, Log No
  const [items, setItems] = useState<RecordItem[]>([]);

  // Log Picker Modal State
  const [isLogPickerOpen, setIsLogPickerOpen] = useState<boolean>(false);
  const [availableTests, setAvailableTests] = useState<PressureTest[]>([]);
  const [logSearch, setLogSearch] = useState<string>('');
  const [isLoadingTests, setIsLoadingTests] = useState<boolean>(false);
  const [selectedPickerLogs, setSelectedPickerLogs] = useState<string[]>([]);

  // Form submission state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch tests for log picker
  const loadAvailableTests = async () => {
    try {
      setIsLoadingTests(true);
      const data = await fetchPressureTests(logSearch);
      setAvailableTests(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingTests(false);
    }
  };

  useEffect(() => {
    if (isLogPickerOpen) {
      const timer = setTimeout(() => {
        loadAvailableTests();
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isLogPickerOpen, logSearch]);

  // Handle adding a log from picker into PTR
  const handleSelectTest = (test: PressureTest, selectedRev?: TestRevision) => {
    const rev = selectedRev || test.revisions?.find(r => r.is_primary) || test.revisions?.[0];
    if (!rev) {
      alert('В этом испытании нет доступных ревизий.');
      return;
    }

    // Check if already attached
    if (attachedLogs.some(l => l.pressure_test_id === test.id && l.test_revision_id === rev.id)) {
      alert(`Лог ${test.log_no} (Ревизия ${rev.revision_id}) уже добавлен в этот протокол.`);
      return;
    }

    const pipeList: string[] = rev.metadata_json?.pipe_numbers || [];

    // Extract artifacts from revision
    const artifacts: RecordLogArtifact[] = (rev.artifacts || []).map((art, idx) => ({
      artifact_id: art.id,
      source: 'log_artifact',
      category: (art.category as any) || (art.file_type === 'graph_png' ? 'other' : 'other'),
      name: art.name,
      storage_key: art.relative_path,
      sha256: art.sha256,
      position: idx,
      is_included_in_pdf: true
    }));

    const newLog: RecordLog = {
      pressure_test_id: test.id,
      test_revision_id: rev.id,
      log_no: test.log_no,
      position: attachedLogs.length,
      include_measurement_table: true,
      selected_pipe_numbers: pipeList,
      metadata_snapshot: {
        log_no: test.log_no,
        revision_id: rev.revision_id,
        operator: rev.operator,
        test_pressure: rev.metadata_json?.test_pressure || testPressure,
        system: rev.metadata_json?.system || jobNo,
        project: rev.metadata_json?.project || project,
        ins_no: rev.metadata_json?.ins_no || insNo,
        duration: rev.metrics_json?.duration_formatted || durationMin,
        min_pressure: rev.metrics_json?.min_pressure_bar,
        max_pressure: rev.metrics_json?.max_pressure_bar,
        mean_pressure: rev.metrics_json?.mean_pressure_bar,
        total_delta: rev.metrics_json?.total_delta_bar,
        evaluation_status: rev.metrics_json?.evaluation_status || 'PASS',
        pipecloud_added: test.pipecloud_added
      },
      artifacts
    };

    setAttachedLogs([...attachedLogs, newLog]);

    // Automatically populate item rows for these pipes
    const newItems: RecordItem[] = pipeList.map((pipe, idx) => ({
      item_no: items.length + idx + 1,
      drawing_no: `DWG-${test.log_no}`,
      spool_no: 'SP-01',
      pipe_number: pipe,
      log_no: test.log_no,
      hold_start_bar: rev.metrics_json?.min_pressure_bar != null ? `${rev.metrics_json.min_pressure_bar} bar` : (rev.metadata_json?.test_pressure || testPressure),
      hold_end_bar: rev.metrics_json?.max_pressure_bar != null ? `${rev.metrics_json.max_pressure_bar} bar` : (rev.metadata_json?.test_pressure || testPressure),
      result: (rev.metrics_json?.evaluation_status === 'FAIL' ? 'FAIL' : 'PASS') as any,
      notes: durationMin
    }));

    setItems([...items, ...newItems]);
    setSelectedPickerLogs((selected) => [...selected, `${test.id}:${rev.id}`]);
  };

  // Reorder attached logs
  const moveLog = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === attachedLogs.length - 1) return;

    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    const updated = [...attachedLogs];
    const temp = updated[index];
    updated[index] = updated[targetIndex];
    updated[targetIndex] = temp;

    // Update positions
    updated.forEach((l, idx) => {
      l.position = idx;
    });

    setAttachedLogs(updated);
  };

  // Remove log from PTR
  const removeLog = (index: number) => {
    const logToRemove = attachedLogs[index];
    const updated = attachedLogs.filter((_, idx) => idx !== index).map((l, idx) => ({ ...l, position: idx }));
    setAttachedLogs(updated);

    // Optionally remove items that belonged to this log
    if (logToRemove.log_no) {
      const filteredItems = items.filter(it => it.log_no !== logToRemove.log_no).map((it, idx) => ({ ...it, item_no: idx + 1 }));
      setItems(filteredItems);
    }
  };

  // Toggle measurement table for a log
  const toggleMeasurementTable = (logIndex: number) => {
    const updated = [...attachedLogs];
    updated[logIndex] = {
      ...updated[logIndex],
      include_measurement_table: !updated[logIndex].include_measurement_table
    };
    setAttachedLogs(updated);
  };

  // Toggle artifact inclusion in PDF
  const toggleArtifactInclusion = (logIndex: number, artIndex: number) => {
    const updated = [...attachedLogs];
    const arts = [...(updated[logIndex].artifacts || [])];
    arts[artIndex] = {
      ...arts[artIndex],
      is_included_in_pdf: !arts[artIndex].is_included_in_pdf
    };
    updated[logIndex] = { ...updated[logIndex], artifacts: arts };
    setAttachedLogs(updated);
  };

  // Pipe table items management
  const addItemRow = () => {
    setItems([
      ...items,
      {
        item_no: items.length + 1,
        drawing_no: 'DWG-001',
        spool_no: 'SP-01',
        pipe_number: `PIPE-${items.length + 1}`,
        log_no: attachedLogs[0]?.log_no || '044-1',
        hold_start_bar: testPressure,
        hold_end_bar: testPressure,
        result: 'PASS',
        notes: durationMin
      }
    ]);
  };

  const removeItemRow = (idx: number) => {
    const updated = items.filter((_, i) => i !== idx).map((it, i) => ({ ...it, item_no: i + 1 }));
    setItems(updated);
  };

  const updateItemField = (idx: number, field: keyof RecordItem, val: any) => {
    const updated = [...items];
    updated[idx] = { ...updated[idx], [field]: val };
    setItems(updated);
  };

  // Page count estimation calculation
  const officialPages = 1 + Math.ceil(Math.max(0, items.length - 7) / 14);
  let compositePages = officialPages;
  const logPageDetails: { log_no: string; info: number; graph: number; photos: number; table: number; total: number }[] = [];

  attachedLogs.forEach((log) => {
    const arts = log.artifacts || [];
    const hasGraph = arts.some(a => (a.category === 'other' || a.name.endsWith('.png')) && a.is_included_in_pdf);
    const photosCount = arts.filter(a => (a.category === 'gauge' || a.category === 'pipe' || a.name.match(/\.(jpg|jpeg)$/i)) && a.is_included_in_pdf).length;
    const photoPages = Math.ceil(photosCount / 2);
    const tablePages = log.include_measurement_table ? 4 : 0;
    const logTotal = 1 + (hasGraph ? 1 : 0) + photoPages + tablePages;

    logPageDetails.push({
      log_no: log.log_no || 'Log',
      info: 1,
      graph: hasGraph ? 1 : 0,
      photos: photoPages,
      table: tablePages,
      total: logTotal
    });

    compositePages += logTotal;
  });

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recordNumber.trim()) {
      setErrorMsg('Номер протокола (Record Number) обязателен.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const payload = {
        record_number: recordNumber.trim(),
        project: project.trim(),
        system: jobNo.trim(),
        ins_no: insNo.trim(),
        test_date: new Date().toISOString().split('T')[0],
        test_medium: testMedium,
        test_pressure: testPressure,
        design_pressure: designPressure,
        duration_min: durationMin,
        foreman_name: foremanName.trim(),
        qc_inspector: 'Quality Inspector',
        client_surveyor: 'Witnessed / Reviewed',
        notes: notes,
        items: items.map(it => ({
          item_no: it.item_no,
          pipe_number: it.pipe_number,
          drawing_no: it.drawing_no || null,
          spool_no: it.spool_no || null,
          log_no: it.log_no || null,
          hold_start_bar: it.hold_start_bar || null,
          hold_end_bar: it.hold_end_bar || null,
          result: it.result,
          notes: it.notes || null
        })),
        logs: attachedLogs.map((l, idx) => ({
          pressure_test_id: l.pressure_test_id,
          test_revision_id: l.test_revision_id,
          position: idx,
          include_measurement_table: l.include_measurement_table,
          selected_pipe_numbers: l.selected_pipe_numbers,
          artifacts: (l.artifacts || []).map(a => ({
            artifact_id: a.artifact_id || null,
            source: a.source,
            category: a.category,
            name: a.name,
            storage_key: a.storage_key || null,
            sha256: a.sha256 || null,
            position: a.position,
            is_included_in_pdf: a.is_included_in_pdf
          }))
        }))
      };

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch('/api/v1/records', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Ошибка создания протокола (${res.status})`);
      }

      const created = await res.json();
      onSuccess(created);
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось сохранить протокол.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" style={{ maxWidth: '1080px', width: '95vw', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
          
          {/* Modal Header */}
          <div className="modal-header">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <FileSpreadsheet size={22} color="var(--accent-amber)" />
                <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {t('btn_create_ptr')} (Composite Builder)
                </span>
                <span className="status-badge draft">DRAFT</span>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                Официальный протокол испытаний ARDOR + сводный пакет с графиками, фото и таблицами измерений
              </div>
            </div>

            <button type="button" onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <X size={22} />
            </button>
          </div>

          {/* Modal Body */}
          <form onSubmit={handleSubmit} style={{ overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {errorMsg && (
              <div className="error-banner" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1rem', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid var(--accent-rose)', borderRadius: 'var(--radius-md)', color: 'var(--accent-rose)' }}>
                <AlertCircle size={18} />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* SECTION 1: Document Metadata */}
            <div style={{ background: 'var(--bg-inset-40)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-amber)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <FileText size={16} />
                <span>1. Основные реквизиты протокола (Official ARDOR Header)</span>
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.9rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Record Number (Номер протокола) *
                  </label>
                  <input
                    type="text"
                    required
                    className="search-input"
                    value={recordNumber}
                    onChange={(e) => setRecordNumber(e.target.value)}
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Inspection Number (INS No.)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={insNo}
                    onChange={(e) => setInsNo(e.target.value)}
                    placeholder="e.g. Inspection 044"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Project (Проект)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={project}
                    onChange={(e) => setProject(e.target.value)}
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    System / Job No. (Система)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={jobNo}
                    onChange={(e) => setJobNo(e.target.value)}
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Test Pressure (Давление испытания)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={testPressure}
                    onChange={(e) => setTestPressure(e.target.value)}
                    placeholder="e.g. 24 bar"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Design Pressure (Расчётное давление)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={designPressure}
                    onChange={(e) => setDesignPressure(e.target.value)}
                    placeholder="e.g. 16 bar"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Test Medium (Среда)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={testMedium}
                    onChange={(e) => setTestMedium(e.target.value)}
                    placeholder="Water / Nitrogen / Air"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Foreman Name (Ответственный прораб)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={foremanName}
                    onChange={(e) => setForemanName(e.target.value)}
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                  />
                </div>
              </div>

              <div style={{ marginTop: '0.9rem' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  Примечания и заключение (Notes)
                </label>
                <input
                  type="text"
                  className="search-input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem' }}
                />
              </div>
            </div>

            {/* SECTION 2: Composite Attached Logs */}
            <div style={{ background: 'var(--bg-inset-40)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-cyan)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Layers size={16} />
                    <span>2. Включенные испытания (Attached Pressure Test Logs) ({attachedLogs.length})</span>
                  </h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Каждый лог формирует отдельный раздел в Full PDF: сводка + график + фото + таблица измерений
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setIsLogPickerOpen(true)}
                  className="btn-primary"
                  style={{ background: 'var(--accent-cyan)', color: '#0F172A', fontWeight: 700, padding: '0.45rem 1rem', fontSize: '0.85rem' }}
                >
                  <Plus size={16} />
                  <span>Добавить лог испытания</span>
                </button>
              </div>

              {attachedLogs.length === 0 ? (
                <div style={{ border: '1px dashed var(--border-color)', padding: '2rem', borderRadius: 'var(--radius-md)', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Layers size={36} color="var(--accent-cyan)" style={{ opacity: 0.5, margin: '0 auto 0.5rem' }} />
                  <div style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Логи испытаний пока не прикреплены</div>
                  <p style={{ fontSize: '0.8rem', maxWidth: '480px', margin: '0.3rem auto 1rem' }}>
                    Нажмите «Добавить лог испытания», чтобы выбрать логи манометра WIKA, автоматически подтянуть графики давления, фотографии и трубы.
                  </p>
                  <button
                    type="button"
                    onClick={() => setIsLogPickerOpen(true)}
                    className="btn-primary"
                    style={{ margin: '0 auto', padding: '0.45rem 1rem', fontSize: '0.85rem' }}
                  >
                    <Plus size={15} />
                    <span>Выбрать лог из базы</span>
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {attachedLogs.map((log, logIdx) => {
                    const snap = log.metadata_snapshot || {};
                    const arts = log.artifacts || [];

                    return (
                      <div
                        key={logIdx}
                        style={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.75rem'
                        }}
                      >
                        {/* Log Item Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.06)', paddingBottom: '0.6rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <span style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--accent-cyan)' }}>
                              #{logIdx + 1}. Log {log.log_no}
                            </span>
                            <span className={`status-badge ${snap.evaluation_status === 'FAIL' ? 'failed' : 'complete'}`}>
                              {snap.evaluation_status || 'PASS'}
                            </span>
                            <span className={`pipecloud-pill ${snap.pipecloud_added ? 'added' : 'not-added'}`} style={{ fontSize: '10px' }}>
                              {snap.pipecloud_added ? 'PIPECLOUD: ADDED' : 'PIPECLOUD: NOT ADDED'}
                            </span>
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                              Ревизия: {snap.revision_id}
                            </span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <button
                              type="button"
                              onClick={() => moveLog(logIdx, 'up')}
                              disabled={logIdx === 0}
                              style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.3rem 0.5rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                              title="Переместить выше"
                            >
                              <ArrowUp size={13} />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveLog(logIdx, 'down')}
                              disabled={logIdx === attachedLogs.length - 1}
                              style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.3rem 0.5rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                              title="Переместить ниже"
                            >
                              <ArrowDown size={13} />
                            </button>
                            <button
                              type="button"
                              onClick={() => removeLog(logIdx)}
                              style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', color: 'var(--accent-rose)', padding: '0.3rem 0.5rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                              title="Удалить из PTR"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>

                        {/* Controls & Toggles */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem', alignItems: 'center' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', background: 'var(--bg-inset-50)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                            <input
                              type="checkbox"
                              checked={log.include_measurement_table}
                              onChange={() => toggleMeasurementTable(logIdx)}
                            />
                            <Table size={16} color="var(--accent-cyan)" />
                            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                              Включить полную таблицу точек CSV (~4 стр.)
                            </span>
                          </label>

                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            Трубы в этом логе ({log.selected_pipe_numbers?.length || 0}):{' '}
                            <span style={{ color: 'var(--accent-cyan)' }}>
                              {log.selected_pipe_numbers?.join(', ') || 'Нет труб'}
                            </span>
                          </div>
                        </div>

                        {/* Artifacts Selection (Photos & Graph) */}
                        {arts.length > 0 && (
                          <div style={{ marginTop: '0.25rem' }}>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                              Материалы и фотографии лога для Full PDF:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                              {arts.map((art, aIdx) => {
                                const isIncluded = art.is_included_in_pdf;
                                const isGraph = art.category === 'other' || art.name.endsWith('.png');

                                return (
                                  <div
                                    key={aIdx}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '0.4rem',
                                      background: isIncluded ? 'rgba(56, 189, 248, 0.1)' : 'var(--bg-inset-40)',
                                      border: isIncluded ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                                      borderRadius: 'var(--radius-sm)',
                                      padding: '0.3rem 0.6rem',
                                      fontSize: '0.75rem',
                                      cursor: 'pointer'
                                    }}
                                    onClick={() => toggleArtifactInclusion(logIdx, aIdx)}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isIncluded}
                                      onChange={() => {}} // Handled by parent div
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                    {isGraph ? <ImageIcon size={13} color="var(--accent-cyan)" /> : <Camera size={13} color="var(--accent-amber)" />}
                                    <span style={{ color: isIncluded ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                      {art.name}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* SECTION 3: Pipes Specification Table */}
            <div style={{ background: 'var(--bg-inset-40)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-emerald)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Table size={16} />
                  <span>3. Спецификация труб для официального бланка ({items.length})</span>
                </h3>

                <button
                  type="button"
                  onClick={addItemRow}
                  style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-primary)', padding: '0.35rem 0.8rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  <Plus size={14} />
                  <span>Добавить строку</span>
                </button>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="record-table" style={{ width: '100%', fontSize: '0.85rem' }}>
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>#</th>
                      <th>Drawing No.</th>
                      <th>Spool / Part No.</th>
                      <th>Pipe Number *</th>
                      <th>Log No.</th>
                      <th style={{ width: '90px' }}>Start (bar)</th>
                      <th style={{ width: '90px' }}>End (bar)</th>
                      <th style={{ width: '100px' }}>Result</th>
                      <th style={{ width: '50px' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((it, idx) => (
                      <tr key={idx}>
                        <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>{it.item_no}</td>
                        <td>
                          <input
                            type="text"
                            value={it.drawing_no || ''}
                            onChange={(e) => updateItemField(idx, 'drawing_no', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', padding: '2px 4px' }}
                            placeholder="Drawing No"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={it.spool_no || ''}
                            onChange={(e) => updateItemField(idx, 'spool_no', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', padding: '2px 4px' }}
                            placeholder="Spool No"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            required
                            value={it.pipe_number}
                            onChange={(e) => updateItemField(idx, 'pipe_number', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--accent-cyan)', fontWeight: 600, padding: '2px 4px' }}
                            placeholder="122153/41"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={it.log_no || ''}
                            onChange={(e) => updateItemField(idx, 'log_no', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', padding: '2px 4px' }}
                            placeholder="044-1"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={it.hold_start_bar || ''}
                            onChange={(e) => updateItemField(idx, 'hold_start_bar', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', padding: '2px 4px' }}
                            placeholder="24.0"
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            value={it.hold_end_bar || ''}
                            onChange={(e) => updateItemField(idx, 'hold_end_bar', e.target.value)}
                            style={{ width: '100%', background: 'transparent', border: '1px solid transparent', color: 'var(--text-primary)', padding: '2px 4px' }}
                            placeholder="24.0"
                          />
                        </td>
                        <td>
                          <select
                            value={it.result}
                            onChange={(e) => updateItemField(idx, 'result', e.target.value as any)}
                            style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: it.result === 'PASS' ? 'var(--accent-emerald)' : 'var(--accent-rose)', borderRadius: 'var(--radius-sm)', padding: '2px 6px', fontWeight: 700 }}
                          >
                            <option value="PASS">PASS</option>
                            <option value="FAIL">FAIL</option>
                            <option value="PENDING">PENDING</option>
                          </select>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            type="button"
                            onClick={() => removeItemRow(idx)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer' }}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* SECTION 4: Live Estimated Page Count Summary */}
            <div style={{ background: 'rgba(56, 189, 248, 0.06)', border: '1px solid rgba(56, 189, 248, 0.25)', padding: '1rem 1.25rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Layers size={16} />
                  <span>Структура и оценка страниц итоговых документов:</span>
                </div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                  • <b>Official ARDOR Record:</b> {officialPages} стр. (до 30–40+ труб с пагинацией)
                  {logPageDetails.map((lp, idx) => (
                    <span key={idx}>
                      {' '}| • <b>Log {lp.log_no}:</b> {lp.total} стр. (сводка: 1, график: {lp.graph}, фото: {lp.photos}, таблица: {lp.table})
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Estimated Full PDF</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
                    ~{compositePages} стр.
                  </div>
                </div>
              </div>
            </div>

            {/* Form Actions Footer */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.55rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              >
                Отмена
              </button>

              <button
                type="submit"
                className="btn-primary"
                disabled={isSubmitting}
                style={{ background: 'var(--accent-amber)', color: '#0F172A', fontWeight: 700, padding: '0.55rem 1.6rem', fontSize: '0.95rem' }}
              >
                {isSubmitting ? (
                  <>
                    <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid #0F172A', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    <span>Сохранение протокола...</span>
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    <span>Сформировать протокол (Create PTR)</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* LOG SEARCH & PICKER MODAL */}
      {isLogPickerOpen && (
        <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => setIsLogPickerOpen(false)}>
          <div className="modal-content" style={{ maxWidth: '820px', width: '90vw', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Search size={20} color="var(--accent-cyan)" />
                <span style={{ fontWeight: 800, fontSize: '1.15rem' }}>
                  Выбор испытания (Pressure Test Log) для включения в PTR
                </span>
              </div>
              <button type="button" onClick={() => setIsLogPickerOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
              <div className="search-input-wrapper">
                <Search size={18} className="search-icon" />
                <input
                  type="text"
                  autoFocus
                  className="search-input"
                  placeholder="Поиск по Log No, номеру трубы, бандлу, оператору, проекту..."
                  value={logSearch}
                  onChange={(e) => setLogSearch(e.target.value)}
                />
              </div>
            </div>

            <div style={{ overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {isLoadingTests ? (
                <div className="empty-state" style={{ padding: '2rem' }}>Поиск испытаний...</div>
              ) : availableTests.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                  Испытания не найдены. Попробуйте изменить строку поиска.
                </div>
              ) : (
                availableTests.map((tItem) => {
                  const primaryRev = tItem.revisions?.find(r => r.is_primary) || tItem.revisions?.[0];
                  const graphArt = primaryRev?.artifacts?.find(a => a.file_type === 'graph_png' || a.name.endsWith('.png'));

                  return (
                    <div
                      key={tItem.id}
                      style={{
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                          padding: '0.55rem 0.75rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                          alignItems: 'center',
                        gap: '1rem',
                        transition: 'border-color 0.15s ease'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                            <span style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--accent-cyan)' }}>
                            Log {tItem.log_no}
                          </span>
                          <span className={`status-badge ${primaryRev?.metrics_json?.evaluation_status === 'FAIL' ? 'failed' : 'complete'}`}>
                            {primaryRev?.metrics_json?.evaluation_status || 'PASS'}
                          </span>
                          <span className={`pipecloud-pill ${tItem.pipecloud_added ? 'added' : 'not-added'}`} style={{ fontSize: '10px' }}>
                            {tItem.pipecloud_added ? 'PIPECLOUD: ADDED' : 'PIPECLOUD: NOT ADDED'}
                          </span>
                        </div>

                          <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                          <span>Давление: <b>{primaryRev?.metadata_json?.test_pressure || 'N/A'}</b></span>
                          <span>Оператор: <b>{primaryRev?.operator || 'N/A'}</b></span>
                          <span>Продолжительность: <b>{primaryRev?.metrics_json?.duration_formatted || '60 min'}</b></span>
                        </div>

                        {primaryRev?.metadata_json?.pipe_numbers && primaryRev.metadata_json.pipe_numbers.length > 0 && (
                          <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
                            {primaryRev.metadata_json.pipe_numbers.map((pn, pIdx) => (
                              <span key={pIdx} className="tag-pipe" style={{ fontSize: '10px' }}>{pn}</span>
                            ))}
                          </div>
                        )}
                      </div>

                      {graphArt && (
                          <div style={{ width: '56px', height: '36px', background: 'var(--bg-inset-80)', borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border-color)', flexShrink: 0 }}>
                          <img
                            src={getArtifactFileUrl(graphArt.id!)}
                            alt="Graph"
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        </div>
                      )}

                      <button
                        type="button"
                          onClick={() => handleSelectTest(tItem, primaryRev)}
                        className="btn-primary"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem', flexShrink: 0 }}
                      >
                        <Plus size={14} />
                          <span>{selectedPickerLogs.includes(`${tItem.id}:${primaryRev?.id}`) ? 'Добавлен' : 'Добавить'}</span>
                      </button>
                    </div>
                  );
                })
              )}
            </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', padding: '0.75rem 1rem', borderTop: '1px solid var(--border-color)' }}>
                <span style={{ marginRight: 'auto', alignSelf: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>Выбрано: {selectedPickerLogs.length}</span>
                <button type="button" onClick={() => { setSelectedPickerLogs([]); setIsLogPickerOpen(false); }} className="btn-primary" disabled={selectedPickerLogs.length === 0} style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem' }}>Добавить выбранные</button>
              </div>
          </div>
        </div>
      )}
    </>
  );
};
