import React, { useState } from 'react';
import { X, Download, CheckCircle2, ShieldCheck } from 'lucide-react';
import { PressureTestRecord } from '../types';
import { getRecordPdfUrl } from '../api';
import { useAuth } from '../context/AuthContext';

interface RecordDetailModalProps {
  record: PressureTestRecord;
  onClose: () => void;
  onUpdate: () => void;
}

export const RecordDetailModal: React.FC<RecordDetailModalProps> = ({ record, onClose, onUpdate }) => {
  const { user, token } = useAuth();
  const [status, setStatus] = useState<string>(record.status);
  const [updating, setUpdating] = useState<boolean>(false);

  const handleStatusChange = async (newStatus: string) => {
    try {
      setUpdating(true);
      const res = await fetch(`/api/v1/records/${record.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        setStatus(newStatus);
        onUpdate();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '900px' }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="log-number" style={{ color: 'var(--accent-amber)', fontSize: '1.4rem' }}>{record.record_number}</span>
              <span className={`status-badge ${status}`}>
                {status}
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
        <div className="modal-body">
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

          {/* Verification & Status Transition */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', gap: '1.5rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>FOREMAN</div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{record.foreman_name || 'N/A'}</div>
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
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {status === 'draft' && (
                    <button
                      onClick={() => handleStatusChange('confirmed')}
                      className="btn-primary"
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}
                      disabled={updating}
                    >
                      <CheckCircle2 size={14} />
                      <span>Confirm Record</span>
                    </button>
                  )}
                  {status === 'confirmed' && (
                    <button
                      onClick={() => handleStatusChange('signed')}
                      className="btn-primary"
                      style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)' }}
                      disabled={updating}
                    >
                      <ShieldCheck size={14} />
                      <span>Mark as Signed</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
