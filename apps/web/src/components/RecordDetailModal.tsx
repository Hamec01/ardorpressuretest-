import React, { useState } from 'react';
import { PressureTestRecord } from '../types';
import { getRecordPdfUrl } from '../api';
import {
  X,
  Download,
  ShieldCheck,
  Edit,
  ExternalLink,
  Eye,
  Table,
  Upload,
  FileSpreadsheet
} from 'lucide-react';
import { SignatureModal } from './SignatureModal';
import { ConfirmRecordModal } from './ConfirmRecordModal';
import { useAuth } from '../context/AuthContext';

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
  const { token } = useAuth();
  const [record, setRecord] = useState<PressureTestRecord>(initialRecord);
  const [activeView, setActiveView] = useState<'pdf' | 'data'>('pdf');
  const [isSignOpen, setIsSignOpen] = useState<boolean>(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState<boolean>(false);
  const [isUploadingCopy, setIsUploadingCopy] = useState<boolean>(false);

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

  const handleSignedCopyUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsUploadingCopy(true);
      const formData = new FormData();
      formData.append('file', file);

      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/v1/records/${record.id}/signed-copy`, {
        method: 'POST',
        headers,
        body: formData
      });

      if (res.ok) {
        const updated = await res.json();
        setRecord(updated);
        onUpdate();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsUploadingCopy(false);
    }
  };

  const pdfUrl = getRecordPdfUrl(record.id);

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" style={{ maxWidth: '980px', width: '94vw' }} onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="modal-header">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <FileSpreadsheet size={22} color="var(--accent-amber)" />
                <span className="log-number" style={{ color: 'var(--accent-amber)', fontSize: '1.3rem' }}>
                  {record.record_number}
                </span>
                <span className={`status-badge ${record.status}`}>
                  {record.status}
                </span>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                {record.ins_no ? `${record.ins_no} — ` : ''}{record.system} — {record.project}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <a
                href={pdfUrl}
                target="_blank"
                rel="noreferrer"
                className="filter-pill"
                style={{ background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', textDecoration: 'none' }}
                title="Открыть PDF в новой вкладке"
              >
                <ExternalLink size={14} />
                <span>Открыть в новой вкладке</span>
              </a>

              <a
                href={pdfUrl}
                className="btn-primary"
                download={`${record.record_number}_Record.pdf`}
                style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
              >
                <Download size={15} />
                <span>Скачать PDF</span>
              </a>

              <button className="modal-close-btn" onClick={onClose}>
                <X size={20} />
              </button>
            </div>
          </div>

          {/* View Mode Toggle & Actions Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className={`filter-pill ${activeView === 'pdf' ? 'active' : ''}`}
                onClick={() => setActiveView('pdf')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
              >
                <Eye size={15} />
                <span>📄 Просмотр PDF бланка (Live PDF)</span>
              </button>
              <button
                type="button"
                className={`filter-pill ${activeView === 'data' ? 'active' : ''}`}
                onClick={() => setActiveView('data')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
              >
                <Table size={15} />
                <span>📋 Данные и трубы ({record.items?.length || 0})</span>
              </button>
            </div>

            {/* Workflow Action Buttons */}
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {record.status === 'draft' && (
                <>
                  <button
                    type="button"
                    className="filter-pill"
                    style={{ background: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)', border: '1px solid var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', fontSize: '0.85rem' }}
                    onClick={() => setIsSignOpen(true)}
                  >
                    <Edit size={14} />
                    <span>🔏 Нарисовать роспись</span>
                  </button>

                  <button
                    type="button"
                    className="btn-primary"
                    style={{ background: 'var(--accent-emerald)', padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                    onClick={() => setIsConfirmOpen(true)}
                  >
                    <ShieldCheck size={15} />
                    <span>Заверить штампом</span>
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Body */}
          <div className="modal-body" style={{ gap: '1.25rem' }}>
            {/* Digital Verification Seal Card if Confirmed */}
            {record.verification_code && (
              <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <ShieldCheck size={22} color="var(--accent-emerald)" />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span>Digitally Verified ARDOR Document</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', background: 'rgba(16, 185, 129, 0.2)', padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-sm)' }}>
                        {record.verification_code}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      Подписано: <strong>{record.confirmed_by_name}</strong> ({record.confirmed_by_role || 'Foreman'})
                    </div>
                    {record.sha256_hash && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.15rem' }}>
                        SHA-256: {record.sha256_hash}
                      </div>
                    )}
                  </div>
                </div>

                <span className="status-badge complete" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}>
                  IMMUTABLE OFFICIAL BLANK
                </span>
              </div>
            )}

            {/* TAB 1: LIVE PDF VIEWER */}
            {activeView === 'pdf' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ width: '100%', height: '620px', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#fff' }}>
                  <iframe
                    src={`${pdfUrl}#toolbar=1&navpanes=0`}
                    title="ARDOR Official Pressure Test Record PDF"
                    style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <span>Официальный бланк ARDOR формируется и сохраняется на сервере в режиме реального времени.</span>
                  <a href={pdfUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'none' }}>
                    Открыть во весь экран ↗
                  </a>
                </div>
              </div>
            ) : (
              /* TAB 2: METADATA & TABLE DATA */
              <>
                {/* Metadata Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST PRESSURE / DESIGN</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {record.test_pressure || 'N/A'} {record.design_pressure ? `/ ${record.design_pressure}` : ''}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MEDIUM / DURATION</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {record.test_medium} ({record.duration_min})
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>NUMBER OR MARK</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                      {record.ins_no || 'N/A'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST DATE</div>
                    <div style={{ fontSize: '1rem', fontWeight: 600 }}>
                      {record.test_date || 'N/A'}
                    </div>
                  </div>
                </div>

                {/* Tested Items Table */}
                <div>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                    Tested Pipeline Elements ({record.items?.length || 0})
                  </h3>
                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', background: 'rgba(15, 23, 42, 0.4)' }}>
                          <th style={{ padding: '0.6rem', textAlign: 'center', width: '40px' }}>#</th>
                          <th style={{ padding: '0.6rem', textAlign: 'left' }}>Piirustus nro (Drawing No)</th>
                          <th style={{ padding: '0.6rem', textAlign: 'left' }}>Systeemi (System)</th>
                          <th style={{ padding: '0.6rem', textAlign: 'left' }}>Osa nro (Part No)</th>
                          <th style={{ padding: '0.6rem', textAlign: 'left' }}>Log No</th>
                          <th style={{ padding: '0.6rem', textAlign: 'center' }}>Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {record.items && record.items.map((it, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                            <td style={{ padding: '0.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>{it.item_no}</td>
                            <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>{it.drawing_no || '-'}</td>
                            <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>{it.spool_no || record.system || '-'}</td>
                            <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{it.pipe_number}</td>
                            <td style={{ padding: '0.5rem', fontFamily: 'var(--font-mono)' }}>{it.log_no || '-'}</td>
                            <td style={{ padding: '0.5rem', textAlign: 'center' }}>
                              <span className={`status-badge ${it.result === 'PASS' ? 'complete' : 'draft'}`}>
                                {it.result}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Remarks & Signatures */}
                <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Witnessed / Reviewed by: </span>
                      <strong style={{ color: 'var(--accent-amber)' }}>{record.foreman_name || 'DE LUCA'}</strong>
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Project: </span>
                      <strong>{record.project}</strong>
                    </div>
                  </div>

                  {record.notes && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Remarks: </span>
                      {record.notes}
                    </div>
                  )}
                </div>

                {/* Upload Physical Signed Scan */}
                <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>Загрузить скан с физической подписью (Physical Scan)</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {record.signed_copy_path ? '✅ Загружен скан подписанной копии' : 'Прикрепите отсканированный подписанный PDF/JPG'}
                    </div>
                  </div>
                  <label className="filter-pill" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem' }}>
                    <Upload size={14} />
                    <span>{isUploadingCopy ? 'Загрузка...' : 'Выбрать файл'}</span>
                    <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleSignedCopyUpload} style={{ display: 'none' }} />
                  </label>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Signature & Confirm Modals */}
      {isSignOpen && (
        <SignatureModal
          record={record}
          onClose={() => setIsSignOpen(false)}
          onSuccess={handleSignatureSuccess}
        />
      )}

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
