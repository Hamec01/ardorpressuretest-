import React, { useEffect, useState } from 'react';
import { X, ShieldAlert, RefreshCw, Clock, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface AuditLogEvent {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_id: string | null;
  actor_name: string | null;
  details_json: any;
  created_at: string;
}

interface AuditLogModalProps {
  onClose: () => void;
}

export const AuditLogModal: React.FC<AuditLogModalProps> = ({ onClose }) => {
  const { token } = useAuth();
  const [events, setEvents] = useState<AuditLogEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('/api/v1/audit?limit=100', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      if (!res.ok) {
        throw new Error(`Failed to load audit logs (${res.status})`);
      }
      const data = await res.json();
      setEvents(data);
    } catch (err: any) {
      setError(err.message || 'Error loading audit trail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '850px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <ShieldAlert size={20} color="var(--accent-amber)" />
            <span style={{ fontSize: '1.2rem', fontWeight: 700 }}>Immutable Audit Trail</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={fetchLogs}
              style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.3rem 0.6rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
            <button className="modal-close-btn" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          {error && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: 'var(--error-text)', padding: '0.75rem', borderRadius: 'var(--radius-md)', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          {loading ? (
            <div className="empty-state">Loading audit events...</div>
          ) : events.length === 0 ? (
            <div className="empty-state">No audit events recorded yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {events.map((ev) => (
                <div
                  key={ev.id}
                  style={{ background: 'var(--bg-inset-60)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={`status-badge ${ev.action === 'created' ? 'complete' : ev.action === 'login' ? 'confirmed' : 'draft'}`}>
                        {ev.action}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
                        {ev.entity_type}
                      </span>
                      {ev.entity_id && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          (ID: {ev.entity_id.slice(0, 8)}...)
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {JSON.stringify(ev.details_json)}
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.15rem', minWidth: '160px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <User size={13} />
                      <span>{ev.actor_name || 'System'}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <Clock size={12} />
                      <span>{new Date(ev.created_at).toLocaleTimeString()} {new Date(ev.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
