import React, { useEffect, useState } from 'react';
import {
  Download,
  FileText,
  FileCode,
  FileSpreadsheet,
  Image as ImageIcon,
  Camera,
  Gauge,
  Pipette,
  AlertCircle,
  Archive,
  Maximize2,
  Sun,
  Moon
} from 'lucide-react';
import { PublicLog } from '../types';
import { fetchPublicShare, publicArtifactThumbnailUrl, publicArtifactUrl, publicZipUrl, resolveLegacyShare } from '../api';
import { useTheme } from '../context/ThemeContext';
import { useI18n } from '../context/LanguageContext';
import { Language } from '../i18n';
import { sortPipeIdentifiers } from '../pipeOrdering';
import { ImageViewer } from './ImageViewer';

/** Either a token link (/s/<token>) or an old number link (/share/<log_no>). */
interface PublicLogViewProps {
  token?: string;
  legacyLogNo?: string;
}

const LANGUAGES: Language[] = ['fi', 'en', 'ru'];

const getArtifactIcon = (type: string) => {
  switch (type) {
    case 'graph_png':
    case 'photo':
      return <ImageIcon size={18} color="var(--accent-cyan)" />;
    case 'excel_xlsx':
      return <FileSpreadsheet size={18} color="var(--accent-emerald)" />;
    case 'report_pdf':
      return <FileText size={18} color="var(--accent-rose)" />;
    case 'source_csv':
    case 'text_txt':
    default:
      return <FileCode size={18} color="var(--accent-amber)" />;
  }
};

export const PublicLogView: React.FC<PublicLogViewProps> = ({ token, legacyLogNo }) => {
  const { theme, toggleTheme } = useTheme();
  const { t, lang, setLang } = useI18n();
  const [log, setLog] = useState<PublicLog | null>(null);
  const [linkToken, setLinkToken] = useState<string | null>(token || null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [failed, setFailed] = useState<boolean>(false);
  const [preview, setPreview] = useState<{ url: string; title: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setFailed(false);
    (async () => {
      const resolved = token || (legacyLogNo ? (await resolveLegacyShare(legacyLogNo)).token : null);
      if (!resolved) throw new Error('no link');
      const data = await fetchPublicShare(resolved);
      if (!cancelled) { setLinkToken(resolved); setLog(data); }
    })()
      .catch(() => { if (!cancelled) setFailed(true); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [token, legacyLogNo]);

  const rev = log?.revision || null;
  const meta = rev?.metadata || {};
  const metrics = rev?.metrics || {};
  const artifacts = rev?.artifacts || [];
  const fileUrl = (id: string) => publicArtifactUrl(linkToken || '', id);

  const graphArtifact = artifacts.find((a) => a.file_type === 'graph_png');
  const photoArtifacts = artifacts.filter((a) => a.file_type === 'photo');
  const otherArtifacts = artifacts.filter((a) => a !== graphArtifact && !photoArtifacts.includes(a));
  const subtitle = [meta.system, meta.project].filter(Boolean).join(' — ');
  const evaluation = metrics.evaluation_status === 'PASS' || metrics.evaluation_status === 'FAIL' ? metrics.evaluation_status : t('not_evaluated');
  const dateLocale = lang === 'fi' ? 'fi-FI' : lang === 'ru' ? 'ru-RU' : 'en-GB';

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-main)' }}>
      <header className="app-header">
        <div className="header-inner">
          <div className="brand-badge" style={{ gap: '0.85rem' }}>
            <img
              src={theme === 'light' ? '/ardor_logo.png' : '/ardor_logo_white.png'}
              alt="ARDOR"
              style={theme === 'light' ? { height: '28px', width: 'auto', display: 'block' } : { height: '28px', width: 'auto', display: 'block', filter: 'brightness(0) invert(1)' }}
              onError={(e) => {
                e.currentTarget.src = '/ardor_logo.png';
              }}
            />
            <div className="public-brand-text" style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '0.85rem' }}>
              <div className="brand-title" style={{ fontSize: '1.05rem', fontWeight: 700 }}>ARDOR Pressure Test</div>
              <div className="brand-subtitle" style={{ fontSize: '0.7rem' }}>{t('share_view_subtitle')}</div>
            </div>
          </div>
          <div className="public-header-actions">
            <div className="auth-langs" role="group" aria-label="Language">
              {LANGUAGES.map((code) => (
                <button key={code} type="button" className={lang === code ? 'active' : ''} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
              ))}
            </div>
            <button
              type="button"
              className="public-theme-button"
              onClick={toggleTheme}
              title={theme === 'light' ? t('mobile_dark_theme') : t('mobile_light_theme')}
              aria-label={theme === 'light' ? t('mobile_dark_theme') : t('mobile_light_theme')}
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </div>
      </header>

      <main className="public-log-main" style={{ maxWidth: '900px', margin: '0 auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {isLoading && <div className="empty-state">{t('share_loading')}</div>}

        {!isLoading && failed && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', padding: '3rem 1rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            <Archive size={40} style={{ opacity: 0.5 }} />
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{t('share_invalid_title')}</div>
            <div style={{ maxWidth: '460px', lineHeight: 1.5 }}>{t('share_invalid_text')}</div>
          </div>
        )}

        {!isLoading && log && !rev && (
          <div className="empty-state">{t('share_no_files')}</div>
        )}

        {!isLoading && log && rev && (
          <>
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', padding: '1.25rem 1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ minWidth: 0 }}>
                  <div className="log-number" style={{ fontSize: '1.5rem' }}>Log {log.log_no}</div>
                  {subtitle && <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.2rem', overflowWrap: 'anywhere' }}>{subtitle}</div>}
                </div>
                <span className={`status-badge ${rev.status}`}>{rev.status}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginTop: '1.1rem' }}>
                <div className="public-metric">
                  <div className="detail-metric-label">{t('metric_test_pressure')}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>{meta.test_pressure || 'N/A'}</div>
                </div>
                <div className="public-metric">
                  <div className="detail-metric-label">{t('card_min_max')}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 700 }}>
                    {metrics.min_pressure_bar != null ? `${Number(metrics.min_pressure_bar).toFixed(1)} / ${Number(metrics.max_pressure_bar).toFixed(1)} bar` : 'N/A'}
                  </div>
                </div>
                <div className="public-metric">
                  <div className="detail-metric-label">{t('metric_duration')}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 700 }}>{metrics.duration_formatted || '00:00:00'}</div>
                </div>
                <div className="public-metric">
                  <div className="detail-metric-label">{t('metric_evaluation')}</div>
                  <div style={{ fontWeight: 700, color: metrics.evaluation_status === 'PASS' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>{evaluation}</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem 1.5rem', marginTop: '1.1rem', fontSize: '0.85rem' }}>
                <div><span style={{ color: 'var(--text-muted)' }}>{t('trace_operator')}: </span><strong>{rev.operator || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>{t('trace_ins_no')}: </span><strong>{meta.ins_no || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>{t('trace_wika')}: </span><strong style={{ overflowWrap: 'anywhere' }}>{meta.wika_nr || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>{t('share_date')}: </span><strong>{new Date(rev.created_at).toLocaleDateString(dateLocale)}</strong></div>
              </div>

              {meta.note && (
                <div style={{ marginTop: '0.85rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>{t('trace_notes')}: </span>{meta.note}
                </div>
              )}

              {Array.isArray(meta.pipe_numbers) && meta.pipe_numbers.length > 0 && (
                <div style={{ marginTop: '0.85rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{t('trace_pipes', { count: meta.pipe_numbers.length })}:</div>
                  <div className="tag-list">
                    {sortPipeIdentifiers(meta.pipe_numbers).map((p: string, i: number) => (
                      <span key={i} className="tag-pipe">{p}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {graphArtifact && (
              <div>
                <div className="detail-section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <ImageIcon size={16} />
                    <span>{t('graph_title')}</span>
                  </h3>
                  <button type="button" className="detail-section-button filter-pill" onClick={() => setPreview({ url: fileUrl(graphArtifact.id), title: graphArtifact.name })}>
                    <Maximize2 size={13} /><span>{t('graph_expand')}</span>
                  </button>
                </div>
                <img
                  src={fileUrl(graphArtifact.id)}
                  alt={t('graph_title')}
                  onClick={() => setPreview({ url: fileUrl(graphArtifact.id), title: graphArtifact.name })}
                  style={{ width: '100%', maxHeight: '360px', objectFit: 'contain', display: 'block', margin: '0 auto', background: 'var(--bg-inset-80)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', cursor: 'zoom-in' }}
                />
              </div>
            )}

            {photoArtifacts.length > 0 && (
              <div>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Camera size={16} />
                  <span>{t('photos_title', { count: photoArtifacts.length })}</span>
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: '0.75rem' }}>
                  {photoArtifacts.map((photo) => {
                    const isGauge = photo.category === 'gauge';
                    const isPipe = photo.category === 'pipe';
                    return (
                      <button
                        key={photo.id}
                        type="button"
                        onClick={() => setPreview({ url: fileUrl(photo.id), title: photo.name })}
                        title={t('image_open_full')}
                        style={{ position: 'relative', display: 'block', height: '130px', padding: 0, borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', background: 'var(--bg-inset-80)', cursor: 'zoom-in' }}
                      >
                        <img src={publicArtifactThumbnailUrl(linkToken || '', photo.id)} alt={photo.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
                        <span style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'var(--bg-inset-85)', padding: '3px 6px', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          {isGauge ? <Gauge size={12} color="var(--accent-cyan)" /> : isPipe ? <Pipette size={12} color="var(--accent-cyan)" /> : null}
                          <span style={{ fontSize: '12px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                            {isGauge ? t('photo_gauge') : isPipe ? t('photo_pipe') : t('photo_other')}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div>
              <div className="detail-section-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  {t('files_title', { count: artifacts.length })}
                </h3>
                {artifacts.length > 0 && linkToken && (
                  <a href={publicZipUrl(linkToken)} className="btn-primary" download style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}>
                    <Download size={14} />
                    <span>{t('share_download_all')}</span>
                  </a>
                )}
              </div>

              {artifacts.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>{t('share_no_files')}</div>
              ) : (
                <div className="artifacts-grid">
                  {[...(graphArtifact ? [graphArtifact] : []), ...otherArtifacts, ...photoArtifacts].map((art) => (
                    <a key={art.id} href={fileUrl(art.id)} download={art.name} className="artifact-card" title={`${t('file_download')}: ${art.name}`}>
                      <div className="artifact-main" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden' }}>
                        {getArtifactIcon(art.file_type)}
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{art.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{(art.size_bytes / 1024).toFixed(1)} KB</div>
                        </div>
                      </div>
                      <Download size={18} color="var(--text-muted)" />
                    </a>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.8rem', justifyContent: 'center', padding: '0.5rem 0', textAlign: 'center' }}>
              <AlertCircle size={13} />
              <span>{t('share_view_only_note')}</span>
            </div>
          </>
        )}
      </main>
      {preview && <ImageViewer url={preview.url} title={preview.title} onClose={() => setPreview(null)} />}
    </div>
  );
};
