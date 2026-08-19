import React from 'react';
import { ShieldCheck, Database, Plus, LogIn, LogOut, ShieldAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface HeaderProps {
  totalCount: number;
  onNewTestClick: () => void;
  onLoginClick: () => void;
  onAuditClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  totalCount,
  onNewTestClick,
  onLoginClick,
  onAuditClick
}) => {
  const { user, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="header-inner">
        <a href="/" className="brand-badge">
          <div className="brand-logo-icon">A</div>
          <div>
            <div className="brand-title">ARDOR Pressure Test</div>
            <div className="brand-subtitle">Pipeline & Vessel Traceability Hub</div>
          </div>
        </a>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <Database size={16} color="var(--accent-cyan)" />
            <span>Indexed: <strong style={{ color: 'var(--text-primary)' }}>{totalCount}</strong> tests</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.1)', padding: '0.3rem 0.75rem', borderRadius: '9999px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
            <ShieldCheck size={15} />
            <span>Local Node Online</span>
          </div>

          {user && (user.role === 'admin' || user.role === 'foreman') && (
            <button
              onClick={onAuditClick}
              style={{ background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)', color: 'var(--accent-amber)', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', fontWeight: 600 }}
              title="View immutable audit trail"
            >
              <ShieldAlert size={15} />
              <span>Audit Trail</span>
            </button>
          )}

          <button
            className="btn-primary"
            onClick={onNewTestClick}
            style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
          >
            <Plus size={16} />
            <span>New Test</span>
          </button>

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', borderLeft: '1px solid var(--border-color)', paddingLeft: '1rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{user.full_name}</span>
                <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: user.role === 'admin' ? 'var(--accent-rose)' : user.role === 'foreman' ? 'var(--accent-cyan)' : 'var(--accent-emerald)', fontWeight: 700 }}>
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-muted)', padding: '0.4rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                title="Sign Out"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <button
              onClick={onLoginClick}
              style={{ background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)', color: 'var(--accent-cyan)', padding: '0.45rem 0.85rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: 600 }}
            >
              <LogIn size={16} />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
