import React, { useState, useRef } from 'react';
import { PressureTest, TestRevision, Artifact } from '../types';
import { getRevisionZipUrl, getArtifactFileUrl, deleteArtifact, deletePressureTest, permanentlyDeletePressureTest, restorePressureTest, updatePipeCloudStatus } from '../api';
import { copyToClipboard } from '../clipboard';
import { useI18n } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import {
  X,
  Download,
  FileText,
  Image as ImageIcon,
  FileSpreadsheet,
  FileCode,
  CheckCircle2,
  Copy,
  Edit3,
  Check,
  Save,
  Maximize2,
  Trash2,
  Cloud,
  CloudOff,
  Camera,
  Plus,
  RefreshCw,
  Share2
} from 'lucide-react';

interface TestDetailModalProps {
  test: PressureTest;
  onClose: () => void;
  onUpdate?: (updatedTest: PressureTest) => void;
  /** Opens the "attach CSV" flow (NewTestModal in attach mode) for this test — only ever called
   * for a draft's primary revision, see the button below. */
  onAttachCsv?: (test: PressureTest) => void;
}

export const TestDetailModal: React.FC<TestDetailModalProps> = ({ test, onClose, onUpdate, onAttachCsv }) => {
  const [currentTest, setCurrentTest] = useState<PressureTest>(test);
  const [selectedRevIndex, setSelectedRevIndex] = useState<number>(0);
  const [copiedSha, setCopiedSha] = useState<string | null>(null);

  // Lightbox Preview for Images
  const [previewImage, setPreviewImage] = useState<{ url: string; title: string } | null>(null);

  // Edit Mode State
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editLogNo, setEditLogNo] = useState<string>('');
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
  const [isUploadingPhotos, setIsUploadingPhotos] = useState<boolean>(false);
  const photoInputRef = useRef<HTMLInputElement | null>(null);

  const { t } = useI18n();
  const { token } = useAuth();
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isTogglingPipeCloud, setIsTogglingPipeCloud] = useState<boolean>(false);
  const [deletingArtifactId, setDeletingArtifactId] = useState<string | null>(null);
  const [linkCopied, setLinkCopied] = useState<boolean>(false);

  const handleShareLink = async () => {
    const url = `${window.location.origin}/share/${encodeURIComponent(currentTest.log_no)}`;
    const ok = await copyToClipboard(url);
    if (ok) {
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } else {
      window.prompt('Скопируйте ссылку на лог:', url);
    }
  };

  const handlePhotosSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    try {
      setIsUploadingPhotos(true);
      const formData = new FormData();
      for (let i = 0; i < e.target.files.length; i++) {
        formData.append('photos', e.target.files[i]);
      }
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const res = await fetch(`/api/v1/tests/${currentTest.log_no}/photos`, {
        method: 'POST',
        headers,
        body: formData
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Не удалось прикрепить фотографии');
      }
      const updatedTest: PressureTest = await res.json();
      setCurrentTest(updatedTest);
      if (onUpdate) {
        onUpdate(updatedTest);
      }
    } catch (err: any) {
      alert(err.message || 'Ошибка загрузки фото');
    } finally {
      setIsUploadingPhotos(false);
      if (photoInputRef.current) {
        photoInputRef.current.value = '';
      }
    }
  };

  const handleTogglePipeCloud = async () => {
    const newStatus = !currentTest.pipecloud_added;
    setIsTogglingPipeCloud(true);
    // Optimistic UI state
    const optimistic: PressureTest = {
      ...currentTest,
      pipecloud_added: newStatus,
      pipecloud_updated_at: new Date().toISOString()
    };
    setCurrentTest(optimistic);

    try {
      const res = await updatePipeCloudStatus(currentTest.log_no, newStatus, token);
      const finalTest: PressureTest = {
        ...currentTest,
        pipecloud_added: res.pipecloud_added,
        pipecloud_updated_at: res.pipecloud_updated_at,
        pipecloud_updated_by_name: res.pipecloud_updated_by_name
      };
      setCurrentTest(finalTest);
      if (onUpdate) {
        onUpdate(finalTest);
      }
    } catch (err: any) {
      setCurrentTest(currentTest); // Rollback
      alert(err.message || 'Failed to update PipeCloud status');
    } finally {
      setIsTogglingPipeCloud(false);
    }
  };

  const handleDeleteTest = async () => {
    const ok = window.confirm(t('delete_test_confirm', { log: currentTest.log_no }));
    if (!ok) return;

    try {
      setIsDeleting(true);
      await deletePressureTest(currentTest.log_no, token);
      if (onUpdate) {
        onUpdate(currentTest);
      }
      onClose();
    } catch (err: any) {
      alert(err.message || 'Failed to delete test');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRestoreTest = async () => {
    try {
      setIsDeleting(true);
      const restored = await restorePressureTest(currentTest.log_no, token);
      setCurrentTest(restored);
      onUpdate?.(restored);
      onClose();
    } catch (err: any) {
      alert(err.message || 'Не удалось восстановить лог');
    } finally {
      setIsDeleting(false);
    }
  };

  const handlePermanentDeleteTest = async () => {
    const ok = window.confirm(t('delete_permanently_confirm', { log: currentTest.log_no }));
    if (!ok) return;

    try {
      setIsDeleting(true);
      await permanentlyDeletePressureTest(currentTest.log_no, token);
      onUpdate?.(currentTest);
      onClose();
    } catch (err: any) {
      alert(err.message || 'Не удалось удалить лог навсегда');
    } finally {
      setIsDeleting(false);
    }
  };

  const revisions = currentTest.revisions || [];
  const currentRev: TestRevision | undefined = revisions[selectedRevIndex] || revisions[0];

  const meta = currentRev?.metadata_json || {};
  const metrics = currentRev?.metrics_json || {};
  const artifacts = currentRev?.artifacts || [];

  // Filter graphs and photos
  const graphArtifact = artifacts.find(
    (a) => a.file_type === 'graph_png' || (a.name.endsWith('.png') && !a.category)
  );

  const photoArtifacts = artifacts.filter(
    (a) => a.file_type === 'photo' || a.category === 'gauge' || a.category === 'pipe' || (a.name.match(/\.(jpg|jpeg|png)$/i) && a !== graphArtifact)
  );

  const handleCopySha = async (sha: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const ok = await copyToClipboard(sha);
    if (ok) {
      setCopiedSha(sha);
      setTimeout(() => setCopiedSha(null), 2000);
    } else {
      window.prompt('Скопируйте SHA-256:', sha);
    }
  };

  const handleDeleteArtifact = async (art: Artifact, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!art.id || !window.confirm(`Удалить файл «${art.name}»?`)) return;

    try {
      setDeletingArtifactId(art.id);
      const updatedTest = await deleteArtifact(art.id, token);
      setCurrentTest(updatedTest);
      onUpdate?.(updatedTest);
    } catch (err: any) {
      alert(err.message || 'Не удалось удалить файл');
    } finally {
      setDeletingArtifactId(null);
    }
  };

  const handleStartEdit = () => {
    setEditLogNo(currentTest.log_no || '');
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
    if (!editLogNo.trim()) {
      setErrorMsg('Log No. не может быть пустым.');
      return;
    }

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
        log_no: editLogNo.trim(),
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

  const handleOpenArtifact = (art: Artifact) => {
    if (!art.id) return;
    const url = getArtifactFileUrl(art.id);
    if (art.file_type === 'photo' || art.file_type === 'graph_png' || art.name.match(/\.(png|jpg|jpeg)$/i)) {
      setPreviewImage({ url, title: art.name });
    } else {
      window.open(url, '_blank');
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
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '960px', width: '92vw', position: 'relative' }} onClick={(e) => e.stopPropagation()}>
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={currentTest.is_archived ? handleRestoreTest : handleDeleteTest}
                disabled={isDeleting}
              className="filter-pill"
                style={{ background: currentTest.is_archived ? 'rgba(16, 185, 129, 0.14)' : 'rgba(244, 63, 94, 0.12)', color: currentTest.is_archived ? 'var(--accent-emerald)' : 'var(--accent-rose)', border: `1px solid ${currentTest.is_archived ? 'var(--accent-emerald)' : 'var(--accent-rose)'}`, display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', padding: '0.5rem 0.8rem', fontSize: '0.85rem' }}
                title={currentTest.is_archived ? t('btn_restore_test') : t('btn_delete_test')}
            >
                {currentTest.is_archived ? <RefreshCw size={14} /> : <Trash2 size={14} />}
                <span>{isDeleting ? t('modal_saving') : currentTest.is_archived ? t('btn_restore_test') : t('btn_delete')}</span>
            </button>

            {currentTest.is_archived && (
              <button
                type="button"
                onClick={handlePermanentDeleteTest}
                disabled={isDeleting}
                className="filter-pill"
                style={{ background: 'var(--accent-rose)', color: '#FFFFFF', border: '1px solid var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', padding: '0.5rem 0.8rem', fontSize: '0.85rem' }}
                title={t('btn_delete_permanently')}
              >
                <Trash2 size={14} />
                <span>{isDeleting ? t('modal_saving') : t('btn_delete_permanently')}</span>
              </button>
            )}

            {/* PipeCloud Manual Toggle */}
            <button
              type="button"
              onClick={handleTogglePipeCloud}
              disabled={isTogglingPipeCloud}
              className="filter-pill"
              style={{
                background: currentTest.pipecloud_added ? 'rgba(16, 185, 129, 0.18)' : 'rgba(239, 68, 68, 0.12)',
                color: currentTest.pipecloud_added ? 'var(--accent-emerald)' : '#f87171',
                border: `1px solid ${currentTest.pipecloud_added ? 'var(--accent-emerald)' : 'rgba(239, 68, 68, 0.4)'}`,
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                cursor: 'pointer',
                padding: '0.5rem 0.85rem',
                fontSize: '0.85rem',
                fontWeight: 600,
                transition: 'all 0.2s ease'
              }}
              title={t('pipecloud_manual_hint')}
            >
              {currentTest.pipecloud_added ? <Cloud size={15} /> : <CloudOff size={15} />}
              <span>
                {currentTest.pipecloud_added ? `☁ ${t('pipecloud_added')}` : `☁ ${t('pipecloud_not_added')}`}
              </span>
            </button>

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

            {!isEditing && currentRev?.status === 'draft' && onAttachCsv && (
              <button
                type="button"
                onClick={() => onAttachCsv(currentTest)}
                className="filter-pill"
                style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)', border: '1px solid var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', padding: '0.5rem 0.9rem', fontSize: '0.85rem', fontWeight: 600 }}
                title="Загрузить CSV-файл измерений и завершить этот черновик"
              >
                <FileSpreadsheet size={15} />
                <span>Прикрепить CSV</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleShareLink}
              className="filter-pill"
              style={{
                background: linkCopied ? 'rgba(16, 185, 129, 0.18)' : 'rgba(56, 189, 248, 0.12)',
                color: linkCopied ? 'var(--accent-emerald)' : 'var(--accent-cyan)',
                border: `1px solid ${linkCopied ? 'var(--accent-emerald)' : 'var(--accent-cyan)'}`,
                display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer',
                padding: '0.5rem 0.85rem', fontSize: '0.85rem', fontWeight: 600
              }}
              title="Скопировать ссылку на этот лог для отправки в чат"
            >
              {linkCopied ? <Check size={15} /> : <Share2 size={15} />}
              <span>{linkCopied ? 'Скопировано!' : 'Ссылка на лог'}</span>
            </button>

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
          </div>
        </div>

        <button
          type="button"
          className="modal-close-btn"
          onClick={onClose}
          title={t('modal_close')}
          aria-label={t('modal_close')}
          style={{ position: 'absolute', top: '0.8rem', right: '0.8rem', zIndex: 2 }}
        >
          <X size={22} />
        </button>

        {/* Body */}
        <div className="modal-body">
          {/* Error Banner */}
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: 'var(--error-text)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', fontSize: '0.9rem' }}>
              {errorMsg}
            </div>
          )}

          {/* Revision Switcher if multiple */}
          {revisions.length > 1 && (
            <div style={{ background: 'var(--bg-inset-40)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
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
            <form onSubmit={handleSaveEdit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: 'var(--bg-inset-60)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--accent-cyan)' }}>
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
                    Log No. *
                  </label>
                  <input
                    type="text"
                    required
                    className="search-input"
                    style={{ background: 'var(--bg-surface)', border: '1px solid var(--accent-cyan)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontWeight: 700 }}
                    placeholder="e.g. 027FED"
                    value={editLogNo}
                    onChange={(e) => setEditLogNo(e.target.value)}
                  />
                </div>

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
                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST PRESSURE</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {meta.test_pressure || 'N/A'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MIN / MAX RECORDED</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(1)} / ${metrics.max_pressure_bar?.toFixed(1)} bar` : 'N/A'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST DURATION</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {metrics.duration_formatted || '00:00:00'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset-60)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EVALUATION PROPOSAL</div>
                    <div style={{ fontWeight: 700, color: metrics.evaluation_status === 'PASS' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                      {metrics.evaluation_status || 'Not Evaluated'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Visual Section: Main Graph Display */}
              {graphArtifact && graphArtifact.id && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <ImageIcon size={16} />
                      <span>График давления и температуры (Pressure Graph)</span>
                    </h3>
                    <button
                      type="button"
                      onClick={() => setPreviewImage({ url: getArtifactFileUrl(graphArtifact.id!), title: graphArtifact.name })}
                      style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.25rem 0.6rem', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                    >
                      <Maximize2 size={12} />
                      <span>Развернуть</span>
                    </button>
                  </div>

                  <div
                    onClick={() => setPreviewImage({ url: getArtifactFileUrl(graphArtifact.id!), title: graphArtifact.name })}
                    style={{
                      background: 'var(--bg-inset-80)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--border-color)',
                      overflow: 'hidden',
                      cursor: 'pointer',
                      textAlign: 'center',
                      maxHeight: '340px'
                    }}
                    title="Нажмите для просмотра в полном размере"
                  >
                    <img
                      src={getArtifactFileUrl(graphArtifact.id)}
                      alt="Pressure Graph"
                      style={{ maxWidth: '100%', maxHeight: '340px', objectFit: 'contain', display: 'block', margin: '0 auto' }}
                    />
                  </div>
                </div>
              )}

              {/* Visual Section: Photos Gallery */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Camera size={16} />
                    <span>Прикреплённые фотографии ({photoArtifacts.length})</span>
                  </h3>
                  <button
                    type="button"
                    onClick={() => photoInputRef.current?.click()}
                    disabled={isUploadingPhotos}
                    style={{
                      background: 'rgba(56, 189, 248, 0.1)',
                      border: '1px solid var(--accent-cyan)',
                      color: 'var(--accent-cyan)',
                      padding: '0.3rem 0.75rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.35rem'
                    }}
                  >
                    {isUploadingPhotos ? (
                      <>
                        <div className="animate-spin" style={{ width: '12px', height: '12px', border: '2px solid var(--accent-cyan)', borderTopColor: 'transparent', borderRadius: '50%' }} />
                        <span>Загрузка...</span>
                      </>
                    ) : (
                      <>
                        <Plus size={14} />
                        <span>Прикрепить фото</span>
                      </>
                    )}
                  </button>
                  <input
                    type="file"
                    ref={photoInputRef}
                    multiple
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={handlePhotosSelected}
                  />
                </div>

                {photoArtifacts.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
                    {photoArtifacts.map((photo, idx) => {
                      if (!photo.id) return null;
                      const photoUrl = getArtifactFileUrl(photo.id);
                      const isGauge = photo.category === 'gauge' || photo.name.toLowerCase().includes('gauge');
                      const isPipe = photo.category === 'pipe' || photo.name.toLowerCase().includes('pipe');
                      const badgeLabel = isGauge ? 'Манометр (Gauge)' : isPipe ? 'Труба (Pipe)' : 'Фото';

                      return (
                        <div
                          key={idx}
                          onClick={() => setPreviewImage({ url: photoUrl, title: photo.name })}
                          style={{
                            position: 'relative',
                            background: 'var(--bg-inset-80)',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border-color)',
                            overflow: 'hidden',
                            cursor: 'pointer',
                            height: '140px'
                          }}
                          title="Нажмите для увеличения"
                        >
                          <img
                            src={photoUrl}
                            alt={photo.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            loading="lazy"
                          />
                          <div
                            style={{
                              position: 'absolute',
                              bottom: '0',
                              left: '0',
                              right: '0',
                              background: 'var(--bg-inset-85)',
                              padding: '4px 6px',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}
                          >
                            <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {badgeLabel}
                            </span>
                            <Maximize2 size={11} color="var(--text-muted)" />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div
                    onClick={() => photoInputRef.current?.click()}
                    style={{
                      padding: '1.25rem',
                      background: 'var(--bg-inset-40)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px dashed var(--border-color)',
                      textAlign: 'center',
                      cursor: 'pointer',
                      color: 'var(--text-muted)',
                      fontSize: '0.85rem'
                    }}
                  >
                    <Camera size={24} style={{ margin: '0 auto 0.4rem', opacity: 0.5 }} />
                    <div>Фотографии манометра или труб пока не прикреплены.</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '0.2rem' }}>
                      Нажмите сюда или на кнопку выше, чтобы добавить фото (.jpg, .jpeg, .png)
                    </div>
                  </div>
                )}
              </div>

              {/* Traceability Metadata */}
              <div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  Traceability & Pipe Identifiers
                </h3>
                <div style={{ background: 'var(--bg-inset-60)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
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

          {/* Actionable Artifacts & Files */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                Файлы и отчёты ревизии ({artifacts.length})
              </h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Нажмите на любой файл (Excel, PDF, TXT, CSV), чтобы открыть или скачать его
              </span>
            </div>

            <div className="artifacts-grid">
              {artifacts.map((art, idx) => {
                if (!art.id) return null;
                const fileUrl = getArtifactFileUrl(art.id);
                return (
                  <div
                    key={idx}
                    className="artifact-card"
                    onClick={() => handleOpenArtifact(art)}
                    style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
                    title={`Открыть ${art.name}`}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden' }}>
                      {getArtifactIcon(art.file_type)}
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {art.name}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {(art.size_bytes / 1024).toFixed(1)} KB • Нажмите для открытия
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <a
                        href={fileUrl}
                        download={art.name}
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: 'var(--text-muted)', padding: '0.2rem', display: 'flex', alignItems: 'center' }}
                        title={`Скачать ${art.name}`}
                      >
                        <Download size={15} />
                      </a>
                      <button
                        onClick={(e) => handleCopySha(art.sha256, e)}
                        style={{ background: 'transparent', border: 'none', color: copiedSha === art.sha256 ? 'var(--accent-emerald)' : 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                        title={`Копировать SHA-256: ${art.sha256}`}
                      >
                        {copiedSha === art.sha256 ? <CheckCircle2 size={15} /> : <Copy size={15} />}
                      </button>
                        <button
                          onClick={(e) => handleDeleteArtifact(art, e)}
                          disabled={deletingArtifactId === art.id}
                          style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: deletingArtifactId === art.id ? 'wait' : 'pointer', padding: '0.2rem', display: 'flex', alignItems: 'center' }}
                          title={`Удалить ${art.name}`}
                        >
                          <Trash2 size={15} />
                        </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Lightbox / Fullscreen Image Preview */}
      {previewImage && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1100,
            background: 'rgba(0, 0, 0, 0.88)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem'
          }}
          onClick={() => setPreviewImage(null)}
        >
          <div style={{ position: 'relative', maxWidth: '90vw', maxHeight: '90vh' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', color: '#fff' }}>
              <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{previewImage.title}</span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <a
                  href={previewImage.url}
                  download
                  style={{ color: '#fff', background: 'rgba(255,255,255,0.15)', padding: '0.3rem 0.6rem', borderRadius: 'var(--radius-sm)', textDecoration: 'none', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  <Download size={14} /> Скачать
                </a>
                <button
                  onClick={() => setPreviewImage(null)}
                  style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff', borderRadius: 'var(--radius-sm)', padding: '0.3rem 0.6rem', cursor: 'pointer' }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <img
              src={previewImage.url}
              alt={previewImage.title}
              style={{ maxWidth: '90vw', maxHeight: '82vh', objectFit: 'contain', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};
