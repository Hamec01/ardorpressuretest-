import React, { useState } from 'react';
import { PressureTest, TestRevision } from '../types';
import { getRevisionZipUrl } from '../api';
import { X, Download, FileText, Image as ImageIcon, FileSpreadsheet, FileCode, CheckCircle2, Copy, Edit3, Check, Save } from 'lucide-react';

interface TestDetailModalProps {
  test: PressureTest;
  onClose: () => void;
  onUpdate?: (updatedTest: PressureTest) => void;
}

export const TestDetailModal: React.FC<TestDetailModalProps> = ({ test, onClose, onUpdate }) => {
  const [currentTest, setCurrentTest] = useState<PressureTest>(test);
  const [selectedRevIndex, setSelectedRevIndex] = useState<number>(0);
  const [copiedSha, setCopiedSha] = useState<string | null>(null);

  // Edit Mode State
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editOperator, setEditOperator] = useState<string>('');
  const [editProject, setEditProject] = useState<string>('');
  const [editSystem, setEditSystem] = useState<string>('');
  const [editInsNo, setEditInsNo] = useState<string>('');
  const [editPressure, setEditPressure] = useState<string>('');
  const [editWikaNr, setEditWikaNr] = useState<string>('');
  const [editNote, setEditNote] = useState<string>('');
  const [editPipes, setEditPipes] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const revisions = currentTest.revisions || [];
  const currentRev: TestRevision | undefined = revisions[selectedRevIndex] || revisions[0];

  const meta = currentRev?.metadata_json || {};
  const metrics = currentRev?.metrics_json || {};
  const artifacts = currentRev?.artifacts || [];

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    setTimeout(() => setCopiedSha(null), 2000);
  };

  const handleStartEdit = () => {
    setEditOperator(currentRev?.operator || '');
    setEditProject(meta.project || '');
    setEditSystem(meta.system || '');
    setEditInsNo(meta.ins_no || '');
    setEditPressure(meta.test_pressure || '');
    setEditWikaNr(meta.wika_nr || '');
    setEditNote(meta.note || '');
    setEditPipes((meta.pipe_numbers || []).join('\n'));
    setIsEditing(true);
    setErrorMsg(null);
    setSaveSuccess(false);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentRev) return;

    try {
      setIsSaving(true);
      setErrorMsg(null);

      const pipeList = editPipes
        .split('\n')
        .map((p) => p.trim())
        .filter(Boolean);

      const extractedBundles = pipeList
        .filter((line) => line.includes('/'))
        .map((line) => line.split('/')[0].trim())
        .filter(Boolean);
      const bundleList = Array.from(new Set(extractedBundles));

      const payload = {
        operator: editOperator.trim(),
        project: editProject.trim(),
        system: editSystem.trim(),
        ins_no: editInsNo.trim(),
        test_pressure: editPressure.trim(),
        wika_nr: editWikaNr.trim(),
        note: editNote.trim(),
        pipe_numbers: pipeList,
        bundle_numbers: bundleList,
      };

      const res = await fetch(`/api/v1/tests/${currentTest.log_no}/revisions/${currentRev.revision_id}/metadata`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Ошибка обновления данных (${res.status})`);
      }

      const updatedTest: PressureTest = await res.json();
      setCurrentTest(updatedTest);
      if (onUpdate) {
        onUpdate(updatedTest);
      }
      setIsEditing(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось сохранить изменения.');
    } finally {
      setIsSaving(false);
    }
  };

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case 'graph_png':
      case 'photo':
        return <ImageIcon size={18} color="var(--accent-cyan)" />;
      case 'excel_xlsx':
        return <FileSpreadsheet size={18} color="var(--accent-emerald)" />;
      case 'report_pdf':
        return <FileText size={18} color="var(--accent-rose)" />;
      case 'source_csv':
      case 'text_txt':
      default:
        return <FileCode size={18} color="var(--accent-amber)" />;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '850px' }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="log-number" style={{ fontSize: '1.4rem' }}>Log {currentTest.log_no}</span>
              <span className={`status-badge ${currentRev?.status || 'complete'}`}>
                {currentRev?.status || 'complete'}
              </span>
              {saveSuccess && (
                <span style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Check size={14} /> Сохранено!
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              {meta.system || 'Industrial Pipeline Test'} — {meta.project || 'Project ARDOR'}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {!isEditing && (
              <button
                type="button"
                onClick={handleStartEdit}
                className="filter-pill"
                style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', padding: '0.5rem 0.9rem', fontSize: '0.85rem' }}
              >
                <Edit3 size={15} />
                <span>Редактировать данные</span>
              </button>
            )}

            {currentRev && (
              <a
                href={getRevisionZipUrl(currentTest.log_no, currentRev.revision_id)}
                className="btn-primary"
                download
              >
                <Download size={16} />
                <span>ZIP Package</span>
              </a>
            )}
            <button className="modal-close-btn" onClick={onClose}>
              <X size={22} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Error Banner */}
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', fontSize: '0.9rem' }}>
              {errorMsg}
            </div>
          )}

          {/* Revision Switcher if multiple */}
          {revisions.length > 1 && (
            <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
                REVISION HISTORY ({revisions.length} revisions):
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {revisions.map((rev, idx) => (
                  <button
                    key={rev.id}
                    className={`filter-pill ${selectedRevIndex === idx ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedRevIndex(idx);
                      setIsEditing(false);
                    }}
                  >
                    Rev {rev.revision_id} {rev.is_primary ? '(Primary)' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* EDIT FORM MODE */}
          {isEditing ? (
            <form onSubmit={handleSaveEdit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'rgba(15, 23, 42, 0.6)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--accent-cyan)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--accent-cyan)' }}>
                  ✏️ Редактирование информации испытания (Log {currentTest.log_no})
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Ревизия: {currentRev?.revision_id}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Имя оператора (Operator)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    placeholder="e.g. Matti Meikäläinen"
                    value={editOperator}
                    onChange={(e) => setEditOperator(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Проект (Project)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    placeholder="e.g. ARDOR Pipeline"
                    value={editProject}
                    onChange={(e) => setEditProject(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Система (System / Line)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    placeholder="e.g. Fuel Gas"
                    value={editSystem}
                    onChange={(e) => setEditSystem(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Inspection No.
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    placeholder="e.g. INS-2026-001"
                    value={editInsNo}
                    onChange={(e) => setEditInsNo(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Испытательное давление (Test Pressure)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    placeholder="e.g. 15 bar"
                    value={editPressure}
                    onChange={(e) => setEditPressure(e.target.value)}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Номер манометра WIKA
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                    value={editWikaNr}
                    onChange={(e) => setEditWikaNr(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Примечания / Заметки (Notes)
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  placeholder="e.g. Weather conditions normal"
                  value={editNote}
                  onChange={(e) => setEditNote(e.target.value)}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Номера связок и труб (Pipe Logs, по одному на строку: Bundle/Pipe):
                  </label>
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)' }}>
                    Пример: 122153/41
                  </span>
                </div>
                <textarea
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.75rem', fontSize: '0.9rem', height: '80px', resize: 'vertical', fontFamily: 'Consolas, monospace', lineHeight: 1.4 }}
                  placeholder="122153/41&#10;122153/21&#10;122153/25"
                  value={editPipes}
                  onChange={(e) => setEditPipes(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.5rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
                  disabled={isSaving}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={isSaving}
                  style={{ padding: '0.5rem 1.4rem' }}
                >
                  {isSaving ? (
                    <>
                      <div className="animate-spin" style={{ width: '14px', height: '14px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                      <span>Сохранение...</span>
                    </>
                  ) : (
                    <>
                      <Save size={16} />
                      <span>Сохранить изменения</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          ) : (
            /* VIEW MODE */
            <>
              {/* Key Metrics */}
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  Inspection & Pressure Metrics
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST PRESSURE</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {meta.test_pressure || 'N/A'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MIN / MAX RECORDED</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(2)} / ${metrics.max_pressure_bar?.toFixed(2)} bar` : 'N/A'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST DURATION</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {metrics.duration_formatted || '00:00:00'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EVALUATION PROPOSAL</div>
                    <div style={{ fontWeight: 700, color: metrics.evaluation_status === 'PASS' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                      {metrics.evaluation_status || 'Not Evaluated'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Traceability Metadata */}
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  Traceability & Pipe Identifiers
                </h3>
                <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Operator: </span>
                      <strong style={{ color: 'var(--accent-cyan)' }}>{currentRev?.operator || 'N/A'}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Inspection No: </span>
                      <strong>{meta.ins_no || 'N/A'}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>WIKA Gauge Serial: </span>
                      <strong>{meta.wika_nr || 'N/A'}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Project: </span>
                      <strong>{meta.project || 'ARDOR'}</strong>
                    </div>
                  </div>

                  {meta.note && (
                    <div style={{ marginBottom: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Notes: </span>
                      {meta.note}
                    </div>
                  )}

                  {meta.pipe_numbers && meta.pipe_numbers.length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                        Pipe Numbers ({meta.pipe_numbers.length}):
                      </div>
                      <div className="tag-list">
                        {meta.pipe_numbers.map((p: string, i: number) => (
                          <span key={i} className="tag-pipe" style={{ fontSize: '0.85rem', padding: '0.2rem 0.6rem' }}>
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Artifacts & Provenance */}
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Revision Evidence Artifacts ({artifacts.length})
            </h3>
            <div className="artifacts-grid">
              {artifacts.map((art, idx) => (
                <div key={idx} className="artifact-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                    {getArtifactIcon(art.file_type)}
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{art.name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {(art.size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleCopySha(art.sha256)}
                    style={{ background: 'transparent', border: 'none', color: copiedSha === art.sha256 ? 'var(--accent-emerald)' : 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                    title={`Copy SHA-256: ${art.sha256}`}
                  >
                    {copiedSha === art.sha256 ? <CheckCircle2 size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
