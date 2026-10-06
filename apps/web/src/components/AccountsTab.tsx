import React, { useEffect, useState } from 'react';
import { Check, Copy, KeyRound, Link2, Pencil, Plus, Power, RefreshCw, ShieldCheck, UserRound, Users, X } from 'lucide-react';
import { Account, AccountRole, IssuedPasswordLink } from '../types';
import { ApiError, createAccount, createPasswordLink, fetchAccounts, setAccountPassword, updateAccount } from '../api';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { copyToClipboard } from '../clipboard';

const ROLES: AccountRole[] = ['admin', 'foreman', 'viewer'];
const ROLE_COLOR: Record<string, string> = {
  admin: 'var(--accent-rose)',
  foreman: 'var(--accent-amber)',
  viewer: 'var(--accent-cyan)',
};

type TFn = ReturnType<typeof useI18n>['t'];

function errorText(err: unknown, t: TFn): string {
  if (err instanceof ApiError) {
    const detail = err.message.toLowerCase();
    if (err.status === 409 && detail.includes('username')) return t('acc_err_username_taken');
    if (err.status === 409 && detail.includes('email')) return t('acc_err_email_taken');
    if (err.status === 409 && detail.includes('last active admin')) return t('acc_err_last_admin');
    if (err.status === 409 && detail.includes('yourself')) return t('acc_self_locked');
    if (err.status === 409 && detail.includes('activate')) return t('acc_err_inactive');
    if (err.status === 422 && detail.includes('username')) return t('acc_err_username_format');
    if (err.status === 422 && detail.includes('password')) return t('acc_err_password_length');
  }
  return t('acc_err_generic');
}

function roleLabel(role: string, t: TFn): string {
  if (role === 'admin') return t('acc_role_admin');
  if (role === 'foreman') return t('acc_role_foreman');
  if (role === 'viewer') return t('acc_role_viewer');
  return `${role} · ${t('acc_role_legacy')}`;
}

function useDateFormat() {
  const { lang } = useI18n();
  const locale = lang === 'fi' ? 'fi-FI' : lang === 'ru' ? 'ru-RU' : 'en-GB';
  return (value: string) => new Intl.DateTimeFormat(locale, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}

const PasswordInput: React.FC<{ id: string; value: string; onChange: (v: string) => void; autoComplete?: string }> = ({ id, value, onChange, autoComplete = 'new-password' }) => {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  return (
    <div className="account-password-field">
      <input id={id} type={visible ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} spellCheck={false} autoCapitalize="none" />
      <button type="button" onClick={() => setVisible((v) => !v)}>{visible ? t('acc_hide_password') : t('acc_show_password')}</button>
    </div>
  );
};

const Modal: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => {
  const { t } = useI18n();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-overlay">
      <div className="modal-content compact-modal" style={{ maxWidth: '480px' }} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <span style={{ fontSize: '1.1rem', fontWeight: 700, overflowWrap: 'anywhere' }}>{title}</span>
          <button type="button" className="modal-close-btn" onClick={onClose} title={t('modal_close')} aria-label={t('modal_close')}><X size={20} /></button>
        </div>
        <div className="modal-body account-form">{children}</div>
      </div>
    </div>
  );
};

const RoleSelect: React.FC<{ value: string; onChange: (r: AccountRole) => void; disabled?: boolean }> = ({ value, onChange, disabled }) => {
  const { t } = useI18n();
  return (
    <div className="account-role-options" role="radiogroup" aria-label={t('acc_field_role')}>
      {ROLES.map((role) => (
        <label key={role} className={`account-role-option${value === role ? ' selected' : ''}${disabled ? ' disabled' : ''}`} style={{ ['--role-color' as string]: ROLE_COLOR[role] }}>
          <input type="radio" name="account-role" value={role} checked={value === role} disabled={disabled} onChange={() => onChange(role)} />
          <span><strong>{roleLabel(role, t)}</strong><small>{t(`acc_role_${role}_hint` as 'acc_role_admin_hint')}</small></span>
        </label>
      ))}
    </div>
  );
};

const LinkResult: React.FC<{ name: string; link: IssuedPasswordLink; onClose: () => void }> = ({ name, link, onClose }) => {
  const { t } = useI18n();
  const formatDate = useDateFormat();
  const [copied, setCopied] = useState(false);
  return (
    <Modal title={t('acc_link_title', { name })} onClose={onClose}>
      <p className="account-note">{t('acc_link_note', { date: formatDate(link.expires_at) })}</p>
      <div className="account-link-box">{link.url}</div>
      <button type="button" className="btn-primary" onClick={async () => setCopied(await copyToClipboard(link.url))} style={{ justifyContent: 'center' }}>
        {copied ? <Check size={16} /> : <Copy size={16} />}<span>{copied ? t('acc_copied') : t('acc_copy')}</span>
      </button>
      <button type="button" className="filter-pill" onClick={onClose} style={{ justifyContent: 'center' }}>{t('acc_done')}</button>
    </Modal>
  );
};

const CreateAccount: React.FC<{ onClose: () => void; onCreated: (account: Account, link: IssuedPasswordLink | null) => void }> = ({ onClose, onCreated }) => {
  const { t } = useI18n();
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<AccountRole>('foreman');
  const [manual, setManual] = useState(false);
  const [password, setPassword] = useState('');
  const [requireChange, setRequireChange] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (manual && password.length < 6) { setError(t('acc_err_password_length')); return; }
    setSaving(true); setError(null);
    try {
      const result = await createAccount({
        username: username.trim(), full_name: fullName.trim(), email: email.trim() || null, role,
        password: manual ? password : null, require_password_change: manual ? requireChange : undefined,
      });
      onCreated(result.account, result.password_link);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={t('acc_create')} onClose={onClose}>
      <form onSubmit={submit} className="account-form-fields">
        {error && <div className="account-error">{error}</div>}
        <label>{t('acc_field_full_name')}<input value={fullName} onChange={(e) => setFullName(e.target.value)} required autoFocus /></label>
        <label>{t('acc_field_username')}<input value={username} onChange={(e) => setUsername(e.target.value)} required autoCapitalize="none" autoCorrect="off" spellCheck={false} pattern="[A-Za-z0-9._\-]{3,32}" /><small>{t('acc_field_username_hint')}</small></label>
        <label>{t('acc_field_email')}<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <div className="account-field-label">{t('acc_field_role')}</div>
        <RoleSelect value={role} onChange={setRole} />
        <label className="account-check"><input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} /><span>{t('acc_manual_password')}</span></label>
        {!manual && <p className="account-note">{t('acc_manual_password_hint')}</p>}
        {manual && (
          <>
            <label htmlFor="new-account-password">{t('acc_field_password')}</label>
            <PasswordInput id="new-account-password" value={password} onChange={setPassword} />
            <label className="account-check"><input type="checkbox" checked={requireChange} onChange={(e) => setRequireChange(e.target.checked)} /><span>{t('acc_require_change')}</span></label>
          </>
        )}
        <button type="submit" className="btn-primary" disabled={saving} style={{ justifyContent: 'center' }}><Plus size={16} /><span>{saving ? t('acc_saving') : t('acc_create')}</span></button>
      </form>
    </Modal>
  );
};

const EditAccount: React.FC<{ account: Account; isSelf: boolean; onClose: () => void; onSaved: (a: Account) => void }> = ({ account, isSelf, onClose, onSaved }) => {
  const { t } = useI18n();
  const [fullName, setFullName] = useState(account.full_name || '');
  const [email, setEmail] = useState(account.email || '');
  const [role, setRole] = useState<string>(account.role);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setError(null);
    try {
      const changes: { full_name?: string; email?: string | null; role?: AccountRole } = {};
      if (fullName.trim() !== (account.full_name || '')) changes.full_name = fullName.trim();
      if (email.trim() !== (account.email || '')) changes.email = email.trim() || null;
      if (role !== account.role && ROLES.includes(role as AccountRole)) changes.role = role as AccountRole;
      onSaved(Object.keys(changes).length ? await updateAccount(account.id, changes) : account);
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal title={t('acc_edit_title')} onClose={onClose}>
      <form onSubmit={submit} className="account-form-fields">
        {error && <div className="account-error">{error}</div>}
        <div className="account-note">@{account.username}</div>
        <label>{t('acc_field_full_name')}<input value={fullName} onChange={(e) => setFullName(e.target.value)} required /></label>
        <label>{t('acc_field_email')}<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <div className="account-field-label">{t('acc_field_role')}</div>
        <RoleSelect value={role} onChange={setRole} disabled={isSelf} />
        {isSelf && <p className="account-note">{t('acc_self_locked')}</p>}
        <button type="submit" className="btn-primary" disabled={saving} style={{ justifyContent: 'center' }}><Check size={16} /><span>{saving ? t('acc_saving') : t('acc_save')}</span></button>
      </form>
    </Modal>
  );
};

const SetPassword: React.FC<{ account: Account; isSelf: boolean; onClose: () => void; onSaved: (a: Account) => void }> = ({ account, isSelf, onClose, onSaved }) => {
  const { t } = useI18n();
  const [password, setPassword] = useState('');
  const [requireChange, setRequireChange] = useState(!isSelf);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 6) { setError(t('acc_err_password_length')); return; }
    setSaving(true); setError(null);
    try {
      onSaved(await setAccountPassword(account.id, password, requireChange));
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal title={t('acc_set_password_title', { name: account.full_name || account.username })} onClose={onClose}>
      <form onSubmit={submit} className="account-form-fields">
        {error && <div className="account-error">{error}</div>}
        <label htmlFor="admin-set-password">{t('acc_field_password')}</label>
        <PasswordInput id="admin-set-password" value={password} onChange={setPassword} />
        {!isSelf && <label className="account-check"><input type="checkbox" checked={requireChange} onChange={(e) => setRequireChange(e.target.checked)} /><span>{t('acc_require_change')}</span></label>}
        <p className="account-note">{t('acc_set_password_note')}</p>
        <button type="submit" className="btn-primary" disabled={saving} style={{ justifyContent: 'center' }}><KeyRound size={16} /><span>{saving ? t('acc_saving') : t('acc_save')}</span></button>
      </form>
    </Modal>
  );
};

export const AccountsTab: React.FC = () => {
  const { t } = useI18n();
  const { user } = useAuth();
  const formatDate = useDateFormat();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [settingPassword, setSettingPassword] = useState<Account | null>(null);
  const [linkResult, setLinkResult] = useState<{ name: string; link: IssuedPasswordLink } | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setAccounts(await fetchAccounts()); } catch (err) { setError(errorText(err, t)); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const replace = (updated: Account) => setAccounts((list) => list.map((a) => (a.id === updated.id ? updated : a)));
  const displayName = (a: Account) => a.full_name || a.username;

  const sendLink = async (account: Account) => {
    setBusyId(account.id); setError(null);
    try {
      const link = await createPasswordLink(account.id);
      setLinkResult({ name: displayName(account), link });
      void load();
    } catch (err) { setError(errorText(err, t)); } finally { setBusyId(null); }
  };

  const toggleActive = async (account: Account) => {
    if (account.is_active && !window.confirm(t('acc_confirm_deactivate', { name: displayName(account) }))) return;
    setBusyId(account.id); setError(null);
    try { replace(await updateAccount(account.id, { is_active: !account.is_active })); } catch (err) { setError(errorText(err, t)); } finally { setBusyId(null); }
  };

  const visible = accounts.filter((a) => showAll || a.is_active);

  return (
    <section className="accounts-tab">
      <div className="accounts-head">
        <div>
          <h2><Users size={20} /> {t('acc_title')}</h2>
          <p>{t('acc_subtitle')}</p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} /><span>{t('acc_create')}</span></button>
      </div>

      <div className="accounts-toolbar">
        <div className="filter-pills" style={{ marginTop: 0 }}>
          <button type="button" className={`filter-pill ${!showAll ? 'active' : ''}`} onClick={() => setShowAll(false)}>{t('acc_filter_active')} ({accounts.filter((a) => a.is_active).length})</button>
          <button type="button" className={`filter-pill ${showAll ? 'active' : ''}`} onClick={() => setShowAll(true)}>{t('acc_filter_all')} ({accounts.length})</button>
        </div>
        <button type="button" className="filter-pill" onClick={() => void load()} title={t('btn_refresh')} aria-label={t('btn_refresh')}><RefreshCw size={15} className={loading ? 'animate-spin' : ''} /></button>
      </div>

      {error && <div className="account-error">{error}</div>}
      {loading && accounts.length === 0 ? <div className="empty-state">{t('acc_loading')}</div> : visible.length === 0 ? <div className="empty-state">{t('acc_empty')}</div> : (
        <div className="accounts-list">
          {visible.map((account) => {
            const isSelf = account.id === user?.id;
            const busy = busyId === account.id;
            return (
              <article key={account.id} className={`account-card${account.is_active ? '' : ' inactive'}`}>
                <div className="account-card-top">
                  <div className="account-avatar" style={{ ['--role-color' as string]: ROLE_COLOR[account.role] || 'var(--text-muted)' }}>{(displayName(account)[0] || '?').toUpperCase()}</div>
                  <div className="account-identity">
                    <strong>{displayName(account)}{isSelf && <em> · {t('acc_you')}</em>}</strong>
                    <span>@{account.username}{account.email ? ` · ${account.email}` : ''}</span>
                  </div>
                  <span className="account-role-badge" style={{ ['--role-color' as string]: ROLE_COLOR[account.role] || 'var(--text-muted)' }}>
                    {account.role === 'admin' ? <ShieldCheck size={13} /> : <UserRound size={13} />}{roleLabel(account.role, t)}
                  </span>
                </div>
                <div className="account-status">
                  {!account.is_active && <span className="account-chip danger">{t('acc_status_inactive')}</span>}
                  {account.is_active && account.password_link.status === 'pending' && account.password_link.expires_at && (
                    <span className="account-chip warn">{t('acc_status_link_pending', { date: formatDate(account.password_link.expires_at) })}</span>
                  )}
                  {account.is_active && account.must_change_password && <span className="account-chip info">{t('acc_status_must_change')}</span>}
                  <span className="account-meta">{account.last_login_at ? t('acc_last_login', { date: formatDate(account.last_login_at) }) : t('acc_never_logged_in')}</span>
                </div>
                <div className="account-actions">
                  <button type="button" className="filter-pill" disabled={busy} onClick={() => setEditing(account)}><Pencil size={15} /><span>{t('acc_action_edit')}</span></button>
                  <button type="button" className="filter-pill" disabled={busy || !account.is_active} onClick={() => void sendLink(account)}><Link2 size={15} /><span>{t('acc_action_link')}</span></button>
                  {!isSelf && <button type="button" className="filter-pill" disabled={busy} onClick={() => setSettingPassword(account)}><KeyRound size={15} /><span>{t('acc_action_set_password')}</span></button>}
                  {!isSelf && (
                    <button type="button" className={`filter-pill ${account.is_active ? 'account-danger' : 'account-ok'}`} disabled={busy} onClick={() => void toggleActive(account)}>
                      <Power size={15} /><span>{account.is_active ? t('acc_action_deactivate') : t('acc_action_activate')}</span>
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {creating && (
        <CreateAccount
          onClose={() => setCreating(false)}
          onCreated={(account, link) => {
            setCreating(false);
            setAccounts((list) => [account, ...list]);
            if (link) setLinkResult({ name: displayName(account), link });
          }}
        />
      )}
      {editing && <EditAccount account={editing} isSelf={editing.id === user?.id} onClose={() => setEditing(null)} onSaved={(a) => { replace(a); setEditing(null); }} />}
      {settingPassword && <SetPassword account={settingPassword} isSelf={settingPassword.id === user?.id} onClose={() => setSettingPassword(null)} onSaved={(a) => { replace(a); setSettingPassword(null); }} />}
      {linkResult && <LinkResult name={linkResult.name} link={linkResult.link} onClose={() => setLinkResult(null)} />}
    </section>
  );
};
