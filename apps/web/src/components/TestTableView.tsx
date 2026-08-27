import React, { useMemo, useState } from 'react';
import { PressureTest, TestRevision } from '../types';
import { getRevisionZipUrl } from '../api';
import { useI18n } from '../context/LanguageContext';
import { Download, ExternalLink, User, Calendar, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';

interface TestTableViewProps {
  tests: PressureTest[];
  onSelectTest: (test: PressureTest) => void;
}

type SortKey = 'log_no' | 'system' | 'pressure' | 'min_max' | 'duration' | 'pipes' | 'pipecloud' | 'operator' | 'date' | 'status';
type SortDir = 'asc' | 'desc';

// Natural/numeric-aware compare so "Log 2" sorts before "Log 10" instead of after it. `dir` only
// flips the ordering between two real values — missing values always sort last, in both
// directions, so reversing the sort doesn't surface "no data" rows at the top.
function compareValues(a: string | number | null, b: string | number | null, dir: SortDir = 'asc'): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  const sign = dir === 'asc' ? 1 : -1;
  if (typeof a === 'number' && typeof b === 'number') return sign * (a - b);
  return sign * String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
}

// "HH:MM:SS" / "MM:SS" -> total seconds, for a real numeric sort instead of a string compare.
function parseDurationSeconds(formatted: string | undefined): number | null {
  if (!formatted) return null;
  const parts = formatted.split(':').map((p) => Number(p));
  if (parts.some((p) => Number.isNaN(p))) return null;
  return parts.reduce((total, p) => total * 60 + p, 0);
}

function sortValueFor(row: ReturnType<typeof buildRow>, key: SortKey): string | number | null {
  switch (key) {
    case 'log_no':
      return row.test.log_no || null;
    case 'system':
      return row.meta.system || row.meta.project || null;
    case 'pressure':
      return row.meta.test_pressure || null;
    case 'min_max':
      return row.metrics.min_pressure_bar ?? null;
    case 'duration':
      return parseDurationSeconds(row.metrics.duration_formatted);
    case 'pipes':
      return row.pipes.length > 0 ? row.pipes.slice().sort((a, b) => compareValues(a, b))[0] : null;
    case 'pipecloud':
      return row.test.pipecloud_added ? 1 : 0;
    case 'operator':
      return row.primaryRev?.operator || null;
    case 'date':
      return row.createdAtMs;
    case 'status':
      return row.status;
    default:
      return null;
  }
}

function buildRow(test: PressureTest) {
  const primaryRev: TestRevision | undefined = test.revisions.find((r) => r.is_primary) || test.revisions[0];
  const meta = primaryRev?.metadata_json || {};
  const metrics = primaryRev?.metrics_json || {};
  const pipes = meta.pipe_numbers || [];
  const status = primaryRev?.status || 'complete';
  const createdAtSource = primaryRev?.created_at || test.created_at;
  const createdAtMs = new Date(createdAtSource).getTime();
  const createdDate = new Date(createdAtSource).toLocaleDateString();
  return { test, primaryRev, meta, metrics, pipes, status, createdAtMs, createdDate };
}

export const TestTableView: React.FC<TestTableViewProps> = ({ tests, onSelectTest }) => {
  const { t } = useI18n();
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const rows = useMemo(() => {
    const built = tests.map(buildRow);
    if (!sortKey) return built;
    return built.slice().sort((a, b) => compareValues(sortValueFor(a, sortKey), sortValueFor(b, sortKey), sortDir));
  }, [tests, sortKey, sortDir]);

  const SortableTh: React.FC<{ sortKeyName: SortKey; label: string; align?: 'left' | 'right' }> = ({ sortKeyName, label, align }) => {
    const active = sortKey === sortKeyName;
    const Icon = active ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
    return (
      <th
        onClick={() => handleSort(sortKeyName)}
        style={{ padding: '0.85rem 1rem', cursor: 'pointer', userSelect: 'none', textAlign: align || 'left', color: active ? 'var(--text-primary)' : undefined }}
        title={`Sort by ${label}`}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}>
          {label}
          <Icon size={12} style={{ opacity: active ? 1 : 0.4 }} />
        </span>
      </th>
    );
  };

  return (
    <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ background: 'var(--bg-inset-60)', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <SortableTh sortKeyName="log_no" label={t('col_log_no')} />
              <SortableTh sortKeyName="system" label={t('col_system_project')} />
              <SortableTh sortKeyName="pressure" label={t('col_target_p')} />
              <SortableTh sortKeyName="min_max" label={t('col_min_max')} />
              <SortableTh sortKeyName="duration" label={t('col_duration')} />
              <SortableTh sortKeyName="pipes" label={t('col_pipes')} />
              <SortableTh sortKeyName="pipecloud" label={t('pipecloud_status')} />
              <SortableTh sortKeyName="operator" label={t('col_operator')} />
              <SortableTh sortKeyName="date" label={t('col_date')} />
              <SortableTh sortKeyName="status" label={t('col_status')} />
              <th style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>{t('col_actions')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ test, primaryRev, meta, metrics, pipes, status, createdDate }) => {
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

                  {/* PipeCloud Status */}
                  <td style={{ padding: '0.85rem 1rem' }}>
                    {test.pipecloud_added ? (
                      <span
                        style={{
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#10b981',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '9999px',
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.2rem'
                        }}
                        title={test.pipecloud_updated_by_name ? `Added to PipeCloud by ${test.pipecloud_updated_by_name}` : 'Added to PipeCloud'}
                      >
                        ☁ {t('pipecloud_added')}
                      </span>
                    ) : (
                      <span
                        style={{
                          background: 'rgba(239, 68, 68, 0.1)',
                          color: '#f87171',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '9999px',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.2rem'
                        }}
                      >
                        ☁ {t('pipecloud_not_added')}
                      </span>
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
