import React, { useEffect, useState } from 'react';
import { Check, Copy, Globe, Link2, Plus, Trash2 } from 'lucide-react';
import { createShare, fetchShares, revokeShare } from '../api';
import { ShareLink } from '../types';
import { copyToClipboard } from '../clipboard';
import { useI18n } from '../context/LanguageContext';

/** Public links of one log (admin/foreman only): token link, legacy number link, revoke. */
export const SharePanel: React.FC<{ logNo: string; refreshKey?: number }> = ({ logNo, refreshKey = 0 }) => {
  const { t, lang } = useI18n();
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [busy, setBusy] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const locale = lang === 'fi' ? 'fi-FI' : lang === 'ru' ? 'ru-RU' : 'en-GB';

  const load = async () => {
    try { setShares(await fetchShares(logNo)); } catch { setShares([]); }
  };
  useEffect(() => { void load(); }, [logNo, refreshKey]);

  const copy = async (share: ShareLink) => {
    if (await copyToClipboard(share.url)) {
      setCopiedId(share.id);
      setTimeout(() => setCopiedId(null), 2000);
    } else {
      window.prompt(t('share_copy_prompt'), share.url);
    }
  };

  const create = async () => {
    setBusy(true); setError(null);
    try {
      const share = await createShare(logNo);
      await load();
      await copy(share);
    } catch {
      setError(t('share_failed'));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (share: ShareLink) => {
    if (!window.confirm(t('share_panel_revoke_confirm'))) return;
    setBusy(true); setError(null);
    try { await revokeShare(share.id); await load(); } catch { setError(t('share_failed')); } finally { setBusy(false); }
  };

  const hasTokenLink = shares.some((share) => !share.legacy);

  return (
    <div className="share-panel">
      <div className="detail-section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Globe size={16} /><span>{t('share_panel_title')}</span>
        </h3>
        {!hasTokenLink && (
          <button type="button" className="detail-section-button filter-pill" disabled={busy} onClick={() => void create()}>
            <Plus size={14} /><span>{t('share_panel_create')}</span>
          </button>
        )}
      </div>
      <p className="share-panel-hint">{t('share_panel_hint')}</p>
      {error && <div className="account-error">{error}</div>}
      {shares.length === 0 ? (
        <div className="share-panel-empty">{t('share_panel_none')}</div>
      ) : (
        <div className="share-panel-list">
          {shares.map((share) => (
            <div key={share.id} className={`share-row${share.legacy ? ' legacy' : ''}`}>
              <div className="share-row-main">
                <strong><Link2 size={14} /> {share.legacy ? t('share_panel_legacy') : t('share_panel_token')}</strong>
                <span className="share-row-url">{share.url}</span>
                <span className="share-row-meta">
                  {share.access_count > 0 ? t('share_panel_opened', { count: share.access_count }) : t('share_panel_never_opened')}
                  {share.last_accessed_at ? ` · ${new Date(share.last_accessed_at).toLocaleString(locale)}` : ''}
                </span>
              </div>
              <div className="share-row-actions">
                <button type="button" className="filter-pill" onClick={() => void copy(share)}>
                  {copiedId === share.id ? <Check size={15} /> : <Copy size={15} />}
                  <span>{copiedId === share.id ? t('share_copied') : t('share_panel_copy')}</span>
                </button>
                <button type="button" className="filter-pill share-revoke" disabled={busy} onClick={() => void revoke(share)}>
                  <Trash2 size={15} /><span>{t('share_panel_revoke')}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
