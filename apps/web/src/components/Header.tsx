import React, { useEffect, useState } from 'react';
import { ShieldCheck, Database, Plus, LogIn, LogOut, ShieldAlert, Globe, Download, X, Monitor, Smartphone, Sun, Moon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';
import { Language } from '../i18n';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

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
  const { theme, toggleTheme } = useTheme();
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);
  const [showInstallHelp, setShowInstallHelp] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as BeforeInstallPromptEvent);
    };
    const handleAppInstalled = () => {
      setIsInstalled(true);
      setInstallPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);
    setIsInstalled(window.matchMedia('(display-mode: standalone)').matches);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const handleInstall = async () => {
    if (isInstalled) return;
    if (installPrompt) {
      await installPrompt.prompt();
      const choice = await installPrompt.userChoice;
      if (choice.outcome === 'accepted') setIsInstalled(true);
      setInstallPrompt(null);
      return;
    }

    setShowInstallHelp(true);
  };

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
            src={theme === 'light' ? '/ardor_logo.png' : '/ardor_logo_white.png'}
            alt="ARDOR"
            style={theme === 'light' ? { height: '28px', width: 'auto', display: 'block' } : { height: '28px', width: 'auto', display: 'block', filter: 'brightness(0) invert(1)' }}
            onError={(e) => {
              e.currentTarget.src = '/ardor_logo.png';
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

          {/* Theme Switcher */}
          <button
            type="button"
            onClick={toggleTheme}
            title={theme === 'light' ? 'Switch to the dark interface' : 'Switch to the light interface'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              borderRadius: 'var(--radius-md)',
              padding: '0.4rem 0.6rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
            <span>{theme === 'light' ? 'Dark' : 'Light'}</span>
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <Database size={15} color="var(--accent-cyan)" />
            <span>{t('indexed_count', { count: totalCount })}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.1)', padding: '0.25rem 0.65rem', borderRadius: '9999px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
            <ShieldCheck size={14} />
            <span>{t('node_online')}</span>
          </div>

          <button
            type="button"
            onClick={() => void handleInstall()}
            disabled={isInstalled}
            style={{ background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.3)', color: 'var(--accent-cyan)', padding: '0.4rem 0.7rem', borderRadius: 'var(--radius-md)', cursor: isInstalled ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', fontWeight: 600, opacity: isInstalled ? 0.65 : 1 }}
            title={isInstalled ? 'ARDOR уже добавлен на устройство' : 'Добавить ARDOR на рабочий стол или главный экран'}
          >
            <Download size={15} />
            <span>{isInstalled ? 'Добавлено' : 'На устройство'}</span>
          </button>

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
      {showInstallHelp && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="install-help-title"
          onClick={() => setShowInstallHelp(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(2, 6, 23, 0.72)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}
        >
          <div
            onClick={(event) => event.stopPropagation()}
            style={{ width: 'min(560px, 100%)', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', boxShadow: '0 24px 70px rgba(0,0,0,0.45)', overflow: 'hidden' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '1rem 1.2rem', borderBottom: '1px solid var(--border-color)' }}>
              <div>
                <div id="install-help-title" style={{ color: 'var(--text-primary)', fontSize: '1.05rem', fontWeight: 700 }}>Добавить ARDOR на устройство</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.25rem' }}>Внутреннее приложение компании</div>
              </div>
              <button type="button" onClick={() => setShowInstallHelp(false)} aria-label="Закрыть инструкцию" style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.35rem' }}><X size={18} /></button>
            </div>

            <div style={{ display: 'grid', gap: '0.9rem', padding: '1.2rem' }}>
              <section style={{ display: 'grid', gap: '0.45rem', padding: '0.9rem', borderRadius: 'var(--radius-md)', background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.22)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-cyan)', fontWeight: 700 }}><Monitor size={17} /> Windows / Chrome</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.55 }}>В меню Chrome нажмите:</div>
                <div style={{ color: 'var(--text-primary)', fontSize: '0.9rem', fontWeight: 700 }}>⋮ → Транслировать, сохранить, поделиться → Установить страницу как приложение…</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>В открывшемся окне нажмите «Установить». Если этого пункта нет, выберите «Создать ярлык» и включите «Открывать в отдельном окне».</div>
              </section>

              <section style={{ display: 'grid', gap: '0.45rem', padding: '0.9rem', borderRadius: 'var(--radius-md)', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.22)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-emerald)', fontWeight: 700 }}><Smartphone size={17} /> Телефон</div>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.55 }}>Откройте меню браузера и выберите «Добавить на главный экран» или «Установить приложение».</div>
              </section>

              <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', lineHeight: 1.5 }}>Адрес ARDOR сохранится автоматически: <strong style={{ color: 'var(--text-secondary)' }}>84.247.130.242:8080</strong>. Покупать домен для внутреннего приложения не нужно.</div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
