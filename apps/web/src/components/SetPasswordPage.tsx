import React, { useEffect, useState } from 'react';
import { CheckCircle2, KeyRound, LinkIcon } from 'lucide-react';
import { fetchPasswordLink, submitPasswordLink } from '../api';
import { PasswordLinkInfo } from '../types';
import { useI18n } from '../context/LanguageContext';
import { Language } from '../i18n';

const LANGUAGES: Language[] = ['fi', 'en', 'ru'];

/** Public page opened from an admin-issued one-time link: /set-password/<token>. */
export const SetPasswordPage: React.FC<{ token: string }> = ({ token }) => {
  const { t, lang, setLang } = useI18n();
  const [info, setInfo] = useState<PasswordLinkInfo | null>(null);
  const [state, setState] = useState<'loading' | 'form' | 'invalid' | 'saved'>('loading');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchPasswordLink(token)
      .then((data) => { setInfo(data); setState('form'); })
      .catch(() => setState('invalid'));
  }, [token]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) { setError(t('acc_err_password_length')); return; }
    if (password !== repeat) { setError(t('setpw_mismatch')); return; }
    setSaving(true); setError(null);
    try {
      await submitPasswordLink(token, password);
      setState('saved');
    } catch {
      setState('invalid');
    } finally {
      setSaving(false);
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

        {state === 'loading' && <p className="auth-muted">{t('setpw_loading')}</p>}

        {state === 'invalid' && (
          <div className="auth-result">
            <LinkIcon size={36} color="var(--accent-amber)" />
            <h1>{t('setpw_invalid_title')}</h1>
            <p className="auth-muted">{t('setpw_invalid_text')}</p>
          </div>
        )}

        {state === 'saved' && info && (
          <div className="auth-result">
            <CheckCircle2 size={40} color="var(--accent-emerald)" />
            <h1>{t('setpw_saved_title')}</h1>
            <p className="auth-muted">{t('setpw_saved_text', { username: info.username })}</p>
            <a className="btn-primary" href="/" style={{ justifyContent: 'center', textDecoration: 'none' }}>{t('setpw_go_login')}</a>
          </div>
        )}

        {state === 'form' && info && (
          <form onSubmit={submit} className="auth-form">
            <h1><KeyRound size={22} /> {info.purpose === 'invite' ? t('setpw_title_invite') : t('setpw_title_reset')}</h1>
            <p className="auth-muted">{t('setpw_greeting', { name: info.full_name || info.username, username: info.username })}</p>
            {/* Lets password managers store the new credential under the right username. */}
            <input type="text" name="username" autoComplete="username" value={info.username} readOnly hidden />
            {error && <div className="account-error">{error}</div>}
            <label htmlFor="setpw-new">{t('setpw_new')}</label>
            <input id="setpw-new" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus required />
            <label htmlFor="setpw-repeat">{t('setpw_repeat')}</label>
            <input id="setpw-repeat" type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
            <button type="submit" className="btn-primary" disabled={saving} style={{ justifyContent: 'center' }}>{saving ? t('acc_saving') : t('setpw_submit')}</button>
          </form>
        )}
      </div>
    </div>
  );
};
