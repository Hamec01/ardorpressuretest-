import React, { useState } from 'react';
import { X, ShieldCheck, AlertTriangle, Check, Lock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { PressureTestRecord } from '../types';

interface ConfirmRecordModalProps {
  record: PressureTestRecord;
  onClose: () => void;
  onSuccess: (updated: PressureTestRecord) => void;
}

export const ConfirmRecordModal: React.FC<ConfirmRecordModalProps> = ({ record, onClose, onSuccess }) => {
  const { user, token } = useAuth();
  const [agreed, setAgreed] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!agreed) {
      setErrorMsg('You must acknowledge the legal engineering integrity declaration.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch(`/api/v1/records/${record.id}/confirm`, {
        method: 'POST',
        headers
      });

      if (!res.ok) {
        throw new Error(`Confirmation failed (${res.status})`);
      }

      const updated = await res.json();
      onSuccess(updated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Error confirming record.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '560px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <ShieldCheck size={22} color="var(--accent-emerald)" />
            <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>Confirm Pressure Test Record</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} disabled={isSubmitting}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body" style={{ gap: '1.25rem' }}>
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '0.75rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <AlertTriangle size={16} color="var(--accent-rose)" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Document Summary */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Document Number:</span>
              <strong style={{ color: 'var(--accent-amber)' }}>{record.record_number}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>System / Project:</span>
              <span>{record.system} ({record.project})</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Pipes in Record:</span>
              <span>{record.items?.length || 0} tested elements</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Signer Identity:</span>
              <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>{user?.full_name} ({user?.role?.toUpperCase()})</span>
            </div>
          </div>

          {/* Security Notice */}
          <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '0.85rem', borderRadius: 'var(--radius-md)', fontSize: '0.8rem', color: '#D1FAE5', lineHeight: 1.5 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, marginBottom: '0.3rem', color: 'var(--accent-emerald)' }}>
              <Lock size={14} />
              <span>Digital Verification Certificate</span>
            </div>
            Confirming this document generates an immutable <strong>Verification Code</strong> and a cryptographic <strong>SHA-256 Digest</strong> timestamped in the audit log. The confirmed revision becomes read-only proof of integrity for client and classification society inspection.
          </div>

          {/* Checkbox */}
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              style={{ marginTop: '0.15rem' }}
            />
            <span>I confirm that the hydrostatic/pneumatic pressure hold tests listed in this record were conducted in accordance with approved procedures and standards.</span>
          </label>

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.55rem 1.1rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: '0.85rem' }}>
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={handleConfirm}
              disabled={isSubmitting || !agreed}
              style={{ background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)', fontSize: '0.85rem' }}
            >
              <Check size={16} />
              <span>{isSubmitting ? 'Confirming...' : 'Confirm & Apply Digital Seal'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
