import React from 'react';
import { PressureTest, TestRevision } from '../types';
import { Calendar, User } from 'lucide-react';

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
