import React from 'react';
import { PressureTest, TestRevision } from '../types';
import { getArtifactFileUrl } from '../api';
import { Calendar, User, Gauge, Pipette, Image as ImageIcon } from 'lucide-react';

interface TestCardProps {
  test: PressureTest;
  onSelect: (test: PressureTest) => void;
}

export const TestCard: React.FC<TestCardProps> = ({ test, onSelect }) => {
  // Get primary or most recent revision
  const primaryRev: TestRevision | undefined = 
    test.revisions.find(r => r.is_primary) || test.revisions[0];

  const meta = primaryRev?.metadata_json || {};
  const metrics = primaryRev?.metrics_json || {};
  const pipes = meta.pipe_numbers || [];
  const bundles = meta.bundle_numbers || [];

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
    ...(gaugePhoto ? [{ photo: gaugePhoto, label: 'Gauge (Манометр)', icon: Gauge }] : []),
    ...(pipePhoto ? [{ photo: pipePhoto, label: 'Pipe (Труба)', icon: Pipette }] : []),
  ];
  // Fallback if not categorized: show first 2 photos
  if (displayPhotos.length === 0 && photos.length > 0) {
    photos.slice(0, 2).forEach((p, idx) => {
      displayPhotos.push({
        photo: p,
        label: idx === 0 ? 'Photo 1' : 'Photo 2',
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
          <span className={`status-badge ${status}`}>
            {status}
          </span>
        </div>

        <div className="metrics-row">
          <div className="metric-item">
            <span className="metric-label">Target</span>
            <span className="metric-val">{meta.test_pressure || 'N/A'}</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Min / Max</span>
            <span className="metric-val">
              {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(1)} / ${metrics.max_pressure_bar?.toFixed(1)}` : 'N/A'}
            </span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Duration</span>
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
                  width: '64px',
                  height: '52px',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  border: '1px solid var(--border-color)',
                  background: 'rgba(15, 23, 42, 0.8)',
                  flexShrink: 0
                }}
                title={label}
              >
                <img
                  src={getArtifactFileUrl(photo.id || '')}
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
                    background: 'rgba(15, 23, 42, 0.85)',
                    color: 'var(--accent-cyan)',
                    fontSize: '8.5px',
                    fontWeight: 600,
                    textAlign: 'center',
                    padding: '1px 2px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}
                >
                  {label.split(' ')[0]}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="tags-section">
          {pipes.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Pipes ({pipes.length}):</div>
              <div className="tag-list">
                {pipes.slice(0, 4).map((p, i) => (
                  <span key={i} className="tag-pipe">{p}</span>
                ))}
                {pipes.length > 4 && <span className="tag-pipe">+{pipes.length - 4} more</span>}
              </div>
            </div>
          )}

          {bundles.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Bundles:</div>
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <Calendar size={14} />
          <span>{createdDate}</span>
        </div>
      </div>
    </div>
  );
};
