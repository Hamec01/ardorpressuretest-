import React, { useState } from 'react';
import { PressureTest, TestRevision } from '../types';
import { createShare, getArtifactThumbnailUrl } from '../api';
import { copyToClipboard } from '../clipboard';
import { sortPipeIdentifiers } from '../pipeOrdering';
import { Calendar, User, Gauge, Pipette, Image as ImageIcon, Share2, Check } from 'lucide-react';
import { useI18n } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

interface TestCardProps {
  test: PressureTest;
  onSelect: (test: PressureTest) => void;
}

export const TestCard: React.FC<TestCardProps> = ({ test, onSelect }) => {
  const { t } = useI18n();
  const { user } = useAuth();
  // Creating a public link is for admin/foreman (ADR-005 §3).
  const canShare = user?.role === 'admin' || user?.role === 'foreman';
  const [linkCopied, setLinkCopied] = useState(false);

  const handleShare = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const { url } = await createShare(test.log_no);
      if (await copyToClipboard(url)) {
        setLinkCopied(true);
        setTimeout(() => setLinkCopied(false), 2000);
      } else {
        window.prompt(t('share_copy_prompt'), url);
      }
    } catch {
      window.alert(t('share_failed'));
    }
  };

  // Get primary or most recent revision
  const primaryRev: TestRevision | undefined = 
    test.revisions.find(r => r.is_primary) || test.revisions[0];

  const meta = primaryRev?.metadata_json || {};
  const metrics = primaryRev?.metrics_json || {};
  const pipes = sortPipeIdentifiers(meta.pipe_numbers || []);
  const bundles = sortPipeIdentifiers(meta.bundle_numbers || []);

  const status = primaryRev?.status || 'complete';
  const createdDate = primaryRev?.created_at 
    ? new Date(primaryRev.created_at).toLocaleDateString()
    : new Date(test.created_at).toLocaleDateString();

  // Find gauge photo and pipe photo
  const photos = (primaryRev?.artifacts || []).filter(
    a => a.file_type === 'photo' || a.name.match(/\.(jpg|jpeg|png)$/i)
  );
  const gaugePhoto = photos.find(p => p.category === 'gauge') || photos.find(p => p.name.toLowerCase().includes('gauge') || p.name.toLowerCase().includes('manometer'));
  const pipePhoto = photos.find(p => p.category === 'pipe') || photos.find(p => p !== gaugePhoto && (p.name.toLowerCase().includes('pipe') || p.name.toLowerCase().includes('tube')));
  const displayPhotos = [
    ...(gaugePhoto ? [{ photo: gaugePhoto, label: t('photo_gauge'), icon: Gauge }] : []),
    ...(pipePhoto ? [{ photo: pipePhoto, label: t('photo_pipe'), icon: Pipette }] : []),
  ];
  // Fallback if not categorized: show first 2 photos
  if (displayPhotos.length === 0 && photos.length > 0) {
    photos.slice(0, 2).forEach((p, idx) => {
      displayPhotos.push({
        photo: p,
        label: `${t('photo_other')} ${idx + 1}`,
        icon: ImageIcon
      });
    });
  }

  return (
    <div className="test-card" onClick={() => onSelect(test)}>
      <div>
        <div className="card-top">
          <div>
            <div className="log-number">Log {test.log_no}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
              {meta.system || 'Industrial Piping System'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
            <span className={`status-badge ${status}`}>
              {status}
            </span>
            {test.pipecloud_added ? (
              <span
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title={test.pipecloud_updated_by_name ? `Added to PipeCloud by ${test.pipecloud_updated_by_name}` : 'Added to PipeCloud'}
              >
                ☁ {t('card_pipecloud')}: {t('pipecloud_added')}
              </span>
            ) : (
              <span
                style={{
                  background: 'rgba(239, 68, 68, 0.1)',
                  color: '#f87171',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}
                title="Not yet marked as added in PipeCloud"
              >
                ☁ {t('pipecloud_not_added')}
              </span>
            )}
          </div>
        </div>

        <div className="metrics-row">
          <div className="metric-item">
            <span className="metric-label">{t('card_target')}</span>
            <span className="metric-val">{meta.test_pressure || 'N/A'}</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">{t('card_min_max')}</span>
            <span className="metric-val">
              {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(1)} / ${metrics.max_pressure_bar?.toFixed(1)}` : 'N/A'}
            </span>
          </div>
          <div className="metric-item">
            <span className="metric-label">{t('card_duration')}</span>
            <span className="metric-val">{metrics.duration_formatted || '00:00:00'}</span>
          </div>
        </div>

        {/* Compact Photo Thumbnails Strip */}
        {displayPhotos.length > 0 && (
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.65rem', marginBottom: '0.2rem' }}>
            {displayPhotos.map(({ photo, label }, idx) => (
              <div
                key={idx}
                style={{
                  position: 'relative',
                  width: '72px',
                  height: '56px',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-inset-80)',
                  flexShrink: 0
                }}
                title={label}
              >
                <img
                  src={getArtifactThumbnailUrl(photo.id || '')}
                  alt={label}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  loading="lazy"
                />
                <span
                  style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '0',
                    right: '0',
                    background: 'var(--bg-inset-85)',
                    color: 'var(--accent-cyan)',
                    fontSize: '11px',
                    fontWeight: 600,
                    textAlign: 'center',
                    padding: '1px 2px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="tags-section">
          {pipes.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>{t('card_pipes', { count: pipes.length })}:</div>
              <div className="tag-list">
                {pipes.slice(0, 4).map((p, i) => (
                  <span key={i} className="tag-pipe">{p}</span>
                ))}
                {pipes.length > 4 && <span className="tag-pipe">{t('card_more', { count: pipes.length - 4 })}</span>}
              </div>
            </div>
          )}

          {bundles.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>{t('card_bundles')}:</div>
              <div className="tag-list">
                {bundles.slice(0, 3).map((b, i) => (
                  <span key={i} className="tag-bundle">{b}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <User size={14} />
          <span>{primaryRev?.operator || 'Operator'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Calendar size={14} />
            <span>{createdDate}</span>
          </div>
          {canShare && <button
            type="button"
            className="card-share-button"
            onClick={handleShare}
            title={t('share_hint')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.25rem',
              background: linkCopied ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
              border: `1px solid ${linkCopied ? 'var(--accent-emerald)' : 'var(--border-color)'}`,
              color: linkCopied ? 'var(--accent-emerald)' : 'var(--text-muted)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.2rem 0.45rem',
              fontSize: '0.72rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            {linkCopied ? <Check size={12} /> : <Share2 size={12} />}
            <span>{linkCopied ? t('card_copied') : t('card_share')}</span>
          </button>}
        </div>
      </div>
    </div>
  );
};
