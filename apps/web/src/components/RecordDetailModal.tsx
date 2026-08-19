import React, { useState } from 'react';
import { X, Download, ShieldCheck, PenTool, Upload, FileCheck } from 'lucide-react';
import { PressureTestRecord } from '../types';
import { getRecordPdfUrl } from '../api';
import { useAuth } from '../context/AuthContext';
import { SignatureModal } from './SignatureModal';
import { ConfirmRecordModal } from './ConfirmRecordModal';

interface RecordDetailModalProps {
  record: PressureTestRecord;
  onClose: () => void;
  onUpdate: () => void;
}

export const RecordDetailModal: React.FC<RecordDetailModalProps> = ({ record: initialRecord, onClose, onUpdate }) => {
  const { user, token } = useAuth();
  const [record, setRecord] = useState<PressureTestRecord>(initialRecord);
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

      const res = await fetch(`/api/v1/records/${record.id}/signed-copy`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        },
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

  return (
    <>
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" style={{ maxWidth: '920px' }} onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="modal-header">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span className="log-number" style={{ color: 'var(--accent-amber)', fontSize: '1.4rem' }}>{record.record_number}</span>
                <span className={`status-badge ${record.status}`}>
                  {record.status}
                </span>
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                {record.system} — {record.project}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <a href={getRecordPdfUrl(record.id)} className="btn-primary" download>
                <Download size={16} />
                <span>Download Official PDF</span>
              </a>
              <button className="modal-close-btn" onClick={onClose}>
                <X size={22} />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="modal-body" style={{ gap: '1.25rem' }}>
            {/* Digital Verification Seal Card if Confirmed */}
            {record.verification_code && (
              <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-md)', padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <ShieldCheck size={24} color="var(--accent-emerald)" />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span>Digitally Verified Document</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', background: 'rgba(16, 185, 129, 0.2)', padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-sm)' }}>{record.verification_code}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      Confirmed by <strong>{record.confirmed_by_name}</strong> ({record.confirmed_by_role}) on {record.confirmed_at ? new Date(record.confirmed_at).toUTCString() : 'N/A'}
                    </div>
                    {record.sha256_hash && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.15rem' }}>
                        SHA-256: {record.sha256_hash}
                      </div>
                    )}
                  </div>
                </div>

                <span className="status-badge complete" style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}>
                  IMMUTABLE REVISION
                </span>
              </div>
            )}

            {/* Metadata Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TARGET PRESSURE</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  {record.test_pressure || 'N/A'}
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MEDIUM / DURATION</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                  {record.test_medium} ({record.duration_min})
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>INSPECTION NO.</div>
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
                1. Tested Pipeline Elements ({record.items?.length || 0})
              </h3>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', background: 'rgba(15, 23, 42, 0.4)' }}>
                      <th style={{ padding: '0.6rem', textAlign: 'center', width: '40px' }}>#</th>
                      <th style={{ padding: '0.6rem', textAlign: 'left' }}>Pipe Number</th>
                      <th style={{ padding: '0.6rem', textAlign: 'left' }}>Dwg / Spool</th>
                      <th style={{ padding: '0.6rem', textAlign: 'left' }}>WIKA Log No</th>
                      <th style={{ padding: '0.6rem', textAlign: 'center' }}>Start bar</th>
                      <th style={{ padding: '0.6rem', textAlign: 'center' }}>End bar</th>
                      <th style={{ padding: '0.6rem', textAlign: 'center' }}>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {record.items && record.items.map((it, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                        <td style={{ padding: '0.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>{it.item_no}</td>
                        <td style={{ padding: '0.5rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>{it.pipe_number}</td>
                        <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>{it.drawing_no || it.spool_no || '-'}</td>
                        <td style={{ padding: '0.5rem', fontFamily: 'var(--font-mono)' }}>Log_{it.log_no || '-'}</td>
                        <td style={{ padding: '0.5rem', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>{it.hold_start_bar || '-'}</td>
                        <td style={{ padding: '0.5rem', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>{it.hold_end_bar || '-'}</td>
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

            {/* Remarks */}
            {record.notes && (
              <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>GENERAL REMARKS</div>
                <div style={{ fontSize: '0.85rem' }}>{record.notes}</div>
              </div>
            )}

            {/* Signatures & Action Toolbar */}
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', gap: '1.5rem' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>FOREMAN</div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{record.foreman_name || 'N/A'}</div>
                    {record.signature_image_path && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.2rem' }}>
                        <FileCheck size={12} />
                        <span>Signature Attached</span>
                      </span>
                    )}
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>QC INSPECTOR</div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{record.qc_inspector || 'N/A'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>CLIENT / SURVEYOR</div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{record.client_surveyor || 'N/A'}</div>
                  </div>
                </div>

                {user && (user.role === 'admin' || user.role === 'foreman') && (
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => setIsSignOpen(true)}
                      className="filter-pill"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
                    >
                      <PenTool size={13} />
                      <span>{record.signature_image_path ? 'Update Signature' : 'Add Signature'}</span>
                    </button>

                    <label
                      className="filter-pill"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', padding: '0.45rem 0.85rem', cursor: 'pointer' }}
                    >
                      <Upload size={13} />
                      <span>{isUploadingCopy ? 'Uploading...' : 'Upload Signed Copy'}</span>
                      <input type="file" accept="application/pdf" onChange={handleSignedCopyUpload} style={{ display: 'none' }} disabled={isUploadingCopy} />
                    </label>

                    {!record.verification_code && (
                      <button
                        onClick={() => setIsConfirmOpen(true)}
                        className="btn-primary"
                        style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem', background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)' }}
                      >
                        <ShieldCheck size={15} />
                        <span>Verify & Confirm Record</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

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
