import React, { useState } from 'react';
import { AlertCircle, KeyRound, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';


export const ChangePasswordModal: React.FC = () => {
  const { changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setError('New passwords do not match.');
      return;
    }
    if (newPassword.length < 6 || newPassword.length > 128) {
      setError('New password must contain 6–128 characters.');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmation('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Password change failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
      <div className="modal-content" style={{ maxWidth: '440px' }}>
        <div className="modal-header">
          <div id="change-password-title" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '1.2rem', fontWeight: 700 }}>
            <KeyRound size={20} color="var(--accent-cyan)" />
            Change password required
          </div>
          <button type="button" className="modal-close-btn" onClick={() => void logout()} title="Sign out" aria-label="Sign out">
            <LogOut size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: '1rem' }}>
          <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.88rem' }}>
            Set a private password before continuing. Spaces and Unicode characters are preserved.
          </p>
          {error && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: 'var(--error-text)', padding: '0.75rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <AlertCircle size={16} color="var(--accent-rose)" />
              <span>{error}</span>
            </div>
          )}
          <label>
            <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Current password</span>
            <input type="password" className="search-input" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required />
          </label>
          <label>
            <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>New password</span>
            <input type="password" className="search-input" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={6} maxLength={128} required />
          </label>
          <label>
            <span style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Confirm new password</span>
            <input type="password" className="search-input" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" minLength={6} maxLength={128} required />
          </label>
          <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
            {loading ? 'Changing password…' : 'Change password'}
          </button>
        </form>
      </div>
    </div>
  );
};
