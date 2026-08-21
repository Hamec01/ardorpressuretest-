import React, { useState } from 'react';
import { PressureTestRecord } from '../types';
import { getRecordPdfUrl, getRecordFullPdfUrl, deleteRecord } from '../api';
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
  Layers
} from 'lucide-react';
import { SignatureModal } from './SignatureModal';
import { ConfirmRecordModal } from './ConfirmRecordModal';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';

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
  const { t } = useI18n();
  const [record, setRecord] = useState<PressureTestRecord>(initialRecord);
  const [activeView, setActiveView] = useState<'official_pdf' | 'full_pdf' | 'data'>('official_pdf');
  const [isSignOpen, setIsSignOpen] = useState<boolean>(false);
  const [isConfirmOpen, setIsConfirmOpen] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const handleDeleteRecord = async () => {
    const confirmed = window.confirm(t('delete_record_confirm', { record: record.record_number }));
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      await deleteRecord(record.id, token);
      onUpdate();
      onClose();
    } catch (err: any) {
      alert(err.message || 'Failed to delete record');
    } finally {
      setIsDeleting(false);
    }
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

  const officialPdfUrl = getRecordPdfUrl(record.id);
  const fullPdfUrl = getRecordFullPdfUrl(record.id);
  const currentActivePdfUrl = activeView === 'full_pdf' ? fullPdfUrl : officialPdfUrl;

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" style={{ maxWidth: '1020px', width: '95vw' }} onClick={(e) => e.stopPropagation()}>
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
              <button
                type="button"
                onClick={handleDeleteRecord}
                disabled={isDeleting}
                className="filter-pill"
                style={{ background: 'rgba(244, 63, 94, 0.12)', color: 'var(--accent-rose)', border: '1px solid var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', fontSize: '0.85rem', cursor: 'pointer' }}
                title={t('btn_delete_record')}
              >
                <Trash2 size={14} />
                <span>{isDeleting ? t('modal_saving') : t('btn_delete')}</span>
              </button>

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

              <button className="modal-close-btn" onClick={onClose}>
                <X size={20} />
              </button>
            </div>
          </div>

          {/* View Mode Toggle & Actions Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
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
              {record.status === 'draft' && (
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
              <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <ShieldCheck size={22} color="var(--accent-emerald)" />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span>{t('verified_badge')}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', background: 'rgba(16, 185, 129, 0.2)', padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-sm)' }}>
                        {record.verification_code}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      {t('signed_by')}: <strong>{record.confirmed_by_name}</strong> ({record.confirmed_by_role || 'Foreman'})
                    </div>
                    {record.official_pdf_sha256 && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.15rem' }}>
                        Official PDF SHA-256: {record.official_pdf_sha256}
                      </div>
                    )}
                    {record.full_pdf_sha256 && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.1rem' }}>
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

            {/* TAB 1 & 2: LIVE PDF VIEWER (Official or Full) */}
            {(activeView === 'official_pdf' || activeView === 'full_pdf') ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ width: '100%', height: '620px', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', background: '#fff' }}>
                  <iframe
                    src={`${currentActivePdfUrl}#toolbar=1&navpanes=0`}
                    title={`ARDOR Pressure Test Record ${activeView === 'full_pdf' ? 'Full Composite' : 'Official'}`}
                    style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
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
                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>KOEPAINE / TEST PRESSURE</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {record.test_pressure || '—'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SUUNNITTELUPAINE / DESIGN P.</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.15rem', fontWeight: 700 }}>
                      {record.design_pressure || '—'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TESTIAINE / MEDIUM</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                      {record.test_medium || 'Water'}
                    </div>
                  </div>

                  <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
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
                  </div>

                  <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                        <thead>
                          <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
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
                          {(record.items || []).map((it) => (
                            <tr key={it.id || it.item_no} style={{ borderBottom: '1px solid var(--border-color)' }}>
                              <td style={{ padding: '0.65rem 0.85rem', color: 'var(--text-muted)' }}>{it.item_no}</td>
                              <td style={{ padding: '0.65rem 0.85rem' }}>{it.drawing_no || it.spool_no || '—'}</td>
                              <td style={{ padding: '0.65rem 0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{it.pipe_number}</td>
                              <td style={{ padding: '0.65rem 0.85rem' }}>{it.log_no ? `Log ${it.log_no}` : '—'}</td>
                              <td style={{ padding: '0.65rem 0.85rem', fontFamily: 'var(--font-mono)' }}>{it.hold_start_bar || '—'}</td>
                              <td style={{ padding: '0.65rem 0.85rem', fontFamily: 'var(--font-mono)' }}>{it.hold_end_bar || '—'}</td>
                              <td style={{ padding: '0.65rem 0.85rem' }}>
                                <span className={`status-badge ${it.result === 'PASS' ? 'complete' : 'pending'}`} style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem' }}>
                                  {it.result}
                                </span>
                              </td>
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
