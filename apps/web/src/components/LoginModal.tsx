import React, { useState } from 'react';
import { X, Lock, User, AlertCircle, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';

interface LoginModalProps {
  onClose: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({ onClose }) => {
  const { login } = useAuth();
  const { t } = useI18n();
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

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
      <div className="modal-content login-modal" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Shield size={20} color="var(--accent-cyan)" />
            <span style={{ fontSize: '1.2rem', fontWeight: 700 }}>{t('login_title')}</span>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} title={t('modal_close')} aria-label={t('modal_close')}>
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
            <label htmlFor="ardor-login-username" style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{t('login_username')}</label>
            <div className="login-field" style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.4rem 0.6rem' }}>
              <User size={16} color="var(--text-muted)" style={{ marginRight: '0.5rem' }} />
              <input
                id="ardor-login-username"
                type="text"
                className="search-input"
                style={{ fontSize: '0.9rem' }}
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="ardor-login-password" style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{t('login_password')}</label>
            <div className="login-field" style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.4rem 0.6rem' }}>
              <Lock size={16} color="var(--text-muted)" style={{ marginRight: '0.5rem' }} />
              <input
                id="ardor-login-password"
                type="password"
                className="search-input"
                style={{ fontSize: '0.9rem' }}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary"
            style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
            disabled={loading}
          >
            {loading ? t('login_progress') : t('login_submit')}
          </button>
        </form>
      </div>
    </div>
  );
};
