import React from 'react';
import { ShieldCheck, Database, Plus, LogIn, LogOut, ShieldAlert, Globe } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { Language } from '../i18n';

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
  const { lang, setLang, t } = useI18n();

  const languages: { code: Language; label: string }[] = [
    { code: 'fi', label: 'FI' },
    { code: 'en', label: 'EN' },
    { code: 'ru', label: 'RU' },
  ];

  return (
    <header className="app-header">
      <div className="header-inner">
        <a href="/" className="brand-badge" style={{ gap: '0.85rem' }}>
          <img
            src="/ardor_logo.png"
            alt="ARDOR"
            style={{ height: '28px', width: 'auto', display: 'block' }}
            onError={(e) => {
              // Fallback if image not rendered
              e.currentTarget.style.display = 'none';
            }}
          />
          <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '0.85rem' }}>
            <div className="brand-title" style={{ fontSize: '1.05rem', fontWeight: 700 }}>
              {t('brand_title')}
            </div>
            <div className="brand-subtitle" style={{ fontSize: '0.7rem' }}>
              {t('brand_subtitle')}
            </div>
          </div>
        </a>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {/* Language Switcher */}
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '2px 4px', gap: '2px' }}>
            <Globe size={13} color="var(--text-muted)" style={{ margin: '0 4px' }} />
            {languages.map((l) => (
              <button
                key={l.code}
                type="button"
                onClick={() => setLang(l.code)}
                style={{
                  background: lang === l.code ? 'var(--brand-primary)' : 'transparent',
                  color: lang === l.code ? '#FFFFFF' : 'var(--text-muted)',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  padding: '3px 7px',
                  fontSize: '0.75rem',
                  fontWeight: lang === l.code ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                {l.label}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <Database size={15} color="var(--accent-cyan)" />
            <span>{t('indexed_count', { count: totalCount })}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.1)', padding: '0.25rem 0.65rem', borderRadius: '9999px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
            <ShieldCheck size={14} />
            <span>{t('node_online')}</span>
          </div>

          {user && (user.role === 'admin' || user.role === 'foreman') && (
            <button
              onClick={onAuditClick}
              style={{ background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.25)', color: 'var(--accent-amber)', padding: '0.4rem 0.7rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', fontWeight: 600 }}
              title="Audit Log"
            >
              <ShieldAlert size={14} />
              <span>{t('btn_audit')}</span>
            </button>
          )}

          <button
            className="btn-primary"
            onClick={onNewTestClick}
            style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem', fontWeight: 600 }}
          >
            <Plus size={15} />
            <span>{t('btn_new_test')}</span>
          </button>

          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', borderLeft: '1px solid var(--border-color)', paddingLeft: '0.85rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{user.full_name}</span>
                <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: user.role === 'admin' ? 'var(--accent-rose)' : user.role === 'foreman' ? 'var(--accent-cyan)' : 'var(--accent-emerald)', fontWeight: 700 }}>
                  {user.role}
                </span>
              </div>
              <button
                onClick={logout}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-muted)', padding: '0.35rem', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }}
                title={t('btn_logout')}
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <button
              onClick={onLoginClick}
              style={{ background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.25)', color: 'var(--accent-cyan)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', fontWeight: 600 }}
            >
              <LogIn size={15} />
              <span>{t('btn_login')}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
