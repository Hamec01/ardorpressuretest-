import React, { useState } from 'react';
import { LogIn } from 'lucide-react';
import { LoginError, useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { Language } from '../i18n';

const LANGUAGES: Language[] = ['fi', 'en', 'ru'];

/** Full-screen sign-in: the application is closed to guests (docs/ACCESS_PLAN_R4-R7.md stage 3). */
export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      if (err instanceof LoginError && err.status === 429) {
        setError(t('login_error_rate', { minutes: Math.max(1, Math.ceil((err.retryAfterSeconds || 60) / 60)) }));
      } else if (err instanceof LoginError && err.status === 401) {
        setError(t('login_error_credentials'));
      } else {
        setError(t('login_error_generic'));
      }
      setPassword('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <img src="/ardor_logo_white.png" alt="ARDOR" />
          <div className="auth-langs" role="group" aria-label="Language">
            {LANGUAGES.map((code) => (
              <button key={code} type="button" className={lang === code ? 'active' : ''} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
            ))}
          </div>
        </div>
        <form onSubmit={submit} className="auth-form">
          <h1><LogIn size={22} /> {t('login_title')}</h1>
          <p className="auth-muted">{t('login_subtitle')}</p>
          {error && <div className="account-error" role="alert">{error}</div>}
          <label htmlFor="login-username">{t('login_username')}</label>
          <input
            id="login-username"
            type="text"
            className="auth-input"
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <label htmlFor="login-password">{t('login_password')}</label>
          <input id="login-password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit" className="btn-primary" disabled={busy} style={{ justifyContent: 'center' }}>{busy ? t('login_progress') : t('login_submit')}</button>
          <p className="auth-muted auth-footnote">{t('login_no_account')}</p>
        </form>
      </div>
    </div>
  );
};
