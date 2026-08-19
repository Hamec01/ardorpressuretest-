import React from 'react';
import { PressureTest, TestRevision } from '../types';
import { getRevisionZipUrl } from '../api';
import { useI18n } from '../context/LanguageContext';
import { Download, ExternalLink, User, Calendar } from 'lucide-react';

interface TestTableViewProps {
  tests: PressureTest[];
  onSelectTest: (test: PressureTest) => void;
}

export const TestTableView: React.FC<TestTableViewProps> = ({ tests, onSelectTest }) => {
  const { t } = useI18n();

  return (
    <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ background: 'rgba(15, 23, 42, 0.6)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_log_no')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_system_project')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_target_p')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_min_max')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_duration')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_pipes')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_operator')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_date')}</th>
              <th style={{ padding: '0.85rem 1rem' }}>{t('col_status')}</th>
              <th style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>{t('col_actions')}</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((test) => {
              const primaryRev: TestRevision | undefined =
                test.revisions.find((r) => r.is_primary) || test.revisions[0];
              const meta = primaryRev?.metadata_json || {};
              const metrics = primaryRev?.metrics_json || {};
              const pipes = meta.pipe_numbers || [];
              const status = primaryRev?.status || 'complete';
              const createdDate = primaryRev?.created_at
                ? new Date(primaryRev.created_at).toLocaleDateString()
                : new Date(test.created_at).toLocaleDateString();

              return (
                <tr
                  key={test.id}
                  onClick={() => onSelectTest(test)}
                  style={{
                    borderBottom: '1px solid var(--border-color)',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(56, 189, 248, 0.04)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  {/* Log No */}
                  <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    Log {test.log_no}
                  </td>

                  {/* System / Project */}
                  <td style={{ padding: '0.85rem 1rem', color: 'var(--text-primary)' }}>
                    <div>{meta.system || 'Industrial Piping'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{meta.project || 'ARDOR'}</div>
                  </td>

                  {/* Target Pressure */}
                  <td style={{ padding: '0.85rem 1rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                    {meta.test_pressure || 'N/A'}
                  </td>

                  {/* Min / Max */}
                  <td style={{ padding: '0.85rem 1rem', fontFamily: 'var(--font-mono)' }}>
                    {metrics.min_pressure_bar != null
                      ? `${metrics.min_pressure_bar.toFixed(1)} / ${metrics.max_pressure_bar?.toFixed(1)}`
                      : 'N/A'}
                  </td>

                  {/* Duration */}
                  <td style={{ padding: '0.85rem 1rem', fontFamily: 'var(--font-mono)' }}>
                    {metrics.duration_formatted || '00:00:00'}
                  </td>

                  {/* Pipes */}
                  <td style={{ padding: '0.85rem 1rem' }}>
                    {pipes.length > 0 ? (
                      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', maxWidth: '200px' }}>
                        {pipes.slice(0, 2).map((p, i) => (
                          <span key={i} className="tag-pipe" style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem' }}>
                            {p}
                          </span>
                        ))}
                        {pipes.length > 2 && (
                          <span className="tag-pipe" style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem' }}>
                            +{pipes.length - 2}
                          </span>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>—</span>
                    )}
                  </td>

                  {/* Operator */}
                  <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <User size={13} />
                      <span>{primaryRev?.operator || 'Operator'}</span>
                    </div>
                  </td>

                  {/* Date */}
                  <td style={{ padding: '0.85rem 1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Calendar size={13} />
                      <span>{createdDate}</span>
                    </div>
                  </td>

                  {/* Status */}
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span className={`status-badge ${status}`} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>
                      {status}
                    </span>
                  </td>

                  {/* Actions */}
                  <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                      <button
                        onClick={() => onSelectTest(test)}
                        className="filter-pill"
                        style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem', background: 'rgba(56, 189, 248, 0.1)', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)' }}
                        title="View Details"
                      >
                        <ExternalLink size={13} />
                        <span>{t('btn_view')}</span>
                      </button>
                      {primaryRev && (
                        <a
                          href={getRevisionZipUrl(test.log_no, primaryRev.revision_id)}
                          download
                          className="filter-pill"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.3rem', background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-emerald)', border: '1px solid var(--accent-emerald)' }}
                          title="Download ZIP Package"
                        >
                          <Download size={13} />
                          <span>ZIP</span>
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
