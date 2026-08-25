import React, { useState } from 'react';
import { X, Lock, User, AlertCircle, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface LoginModalProps {
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ onClose }) => {
  const { login } = useAuth();
  const [username, setUsername] = useState<string>('admin');
  const [password, setPassword] = useState<string>('admin123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);
      await login(username, password);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Shield size={20} color="var(--accent-cyan)" />
            <span style={{ fontSize: '1.2rem', fontWeight: 700 }}>ARDOR Authentication</span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: '1rem' }}>
          {error && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: 'var(--error-text)', padding: '0.75rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <AlertCircle size={16} color="var(--accent-rose)" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Username</label>
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.4rem 0.6rem' }}>
              <User size={16} color="var(--text-muted)" style={{ marginRight: '0.5rem' }} />
              <input
                type="text"
                className="search-input"
                style={{ fontSize: '0.9rem' }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Password</label>
            <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.4rem 0.6rem' }}>
              <Lock size={16} color="var(--text-muted)" style={{ marginRight: '0.5rem' }} />
              <input
                type="password"
                className="search-input"
                style={{ fontSize: '0.9rem' }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          {/* Quick Demo Switchers */}
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Demo Accounts:</div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="filter-pill"
                style={{ fontSize: '0.75rem' }}
                onClick={() => handleQuickFill('admin', 'admin123')}
              >
                Admin
              </button>
              <button
                type="button"
                className="filter-pill"
                style={{ fontSize: '0.75rem' }}
                onClick={() => handleQuickFill('foreman_matti', 'foreman123')}
              >
                Foreman (Matti)
              </button>
              <button
                type="button"
                className="filter-pill"
                style={{ fontSize: '0.75rem' }}
                onClick={() => handleQuickFill('operator_pekka', 'operator123')}
              >
                Operator (Pekka)
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary"
            style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
            disabled={loading}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};
