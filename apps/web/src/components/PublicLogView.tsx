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
  ExternalLink,
  Sun,
  Moon
} from 'lucide-react';
import { PressureTest, TestRevision, Artifact } from '../types';
import { fetchTestByLog, getArtifactFileUrl, getRevisionZipUrl } from '../api';
import { useTheme } from '../context/ThemeContext';

interface PublicLogViewProps {
  logNo: string;
}

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

export const PublicLogView: React.FC<PublicLogViewProps> = ({ logNo }) => {
  const { theme, toggleTheme } = useTheme();
  const [test, setTest] = useState<PressureTest | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setErrorMsg(null);
    fetchTestByLog(logNo)
      .then((data) => {
        if (!cancelled) setTest(data);
      })
      .catch(() => {
        if (!cancelled) setErrorMsg('Log not found. It may have been deleted, or the link is outdated.');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [logNo]);

  const rev: TestRevision | undefined = test?.revisions.find((r) => r.is_primary) || test?.revisions[0];
  const meta = rev?.metadata_json || {};
  const metrics = rev?.metrics_json || {};
  const artifacts: Artifact[] = rev?.artifacts || [];

  const graphArtifact = artifacts.find((a) => a.file_type === 'graph_png');
  const photoArtifacts = artifacts.filter((a) => a.file_type === 'photo');
  const otherArtifacts = artifacts.filter((a) => a !== graphArtifact && !photoArtifacts.includes(a));

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
            <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: '0.85rem' }}>
              <div className="brand-title" style={{ fontSize: '1.05rem', fontWeight: 700 }}>ARDOR Pressure Test</div>
              <div className="brand-subtitle" style={{ fontSize: '0.7rem' }}>Shared log view</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.9rem' }}>
            <button
              type="button"
              onClick={toggleTheme}
              title={theme === 'light' ? 'Switch to the dark interface' : 'Switch to the light interface'}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                borderRadius: 'var(--radius-md)',
                padding: '0.4rem 0.6rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
              <span>{theme === 'light' ? 'Dark' : 'Light'}</span>
            </button>
            <a
              href="/"
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-cyan)', fontSize: '0.85rem', textDecoration: 'none', fontWeight: 600 }}
            >
              <span>Open ARDOR App</span>
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: '900px', margin: '0 auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {isLoading && (
          <div className="empty-state">Loading log…</div>
        )}

        {!isLoading && errorMsg && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
            <Archive size={40} style={{ opacity: 0.5 }} />
            <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{errorMsg}</div>
          </div>
        )}

        {!isLoading && test && rev && (
          <>
            {/* Header Card */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)', padding: '1.25rem 1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                  <div className="log-number" style={{ fontSize: '1.5rem' }}>Log {test.log_no}</div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    {meta.system || 'Industrial Piping System'} — {meta.project || 'ARDOR Project'}
                  </div>
                </div>
                <span className={`status-badge ${rev.status}`}>{rev.status}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginTop: '1.1rem' }}>
                <div style={{ background: 'var(--bg-inset-60)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>TEST PRESSURE</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                    {meta.test_pressure || 'N/A'}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-inset-60)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>MIN / MAX</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 700 }}>
                    {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(1)} / ${metrics.max_pressure_bar?.toFixed(1)} bar` : 'N/A'}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-inset-60)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>DURATION</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: 700 }}>
                    {metrics.duration_formatted || '00:00:00'}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-inset-60)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>EVALUATION</div>
                  <div style={{ fontWeight: 700, color: metrics.evaluation_status === 'PASS' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                    {metrics.evaluation_status || 'Not Evaluated'}
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem 1.5rem', marginTop: '1.1rem', fontSize: '0.85rem' }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Operator: </span><strong>{rev.operator || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Inspection No: </span><strong>{meta.ins_no || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>WIKA Gauge: </span><strong>{meta.wika_nr || 'N/A'}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Date: </span><strong>{new Date(rev.created_at).toLocaleDateString('en-GB')}</strong></div>
              </div>

              {meta.note && (
                <div style={{ marginTop: '0.85rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Notes: </span>{meta.note}
                </div>
              )}

              {meta.pipe_numbers && meta.pipe_numbers.length > 0 && (
                <div style={{ marginTop: '0.85rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                    Pipe Numbers ({meta.pipe_numbers.length}):
                  </div>
                  <div className="tag-list">
                    {meta.pipe_numbers.map((p: string, i: number) => (
                      <span key={i} className="tag-pipe">{p}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Graph */}
            {graphArtifact && graphArtifact.id && (
              <div>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--accent-cyan)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <ImageIcon size={16} />
                  <span>Pressure Graph</span>
                </h3>
                <a href={getArtifactFileUrl(graphArtifact.id)} target="_blank" rel="noreferrer">
                  <img
                    src={getArtifactFileUrl(graphArtifact.id)}
                    alt="Pressure Graph"
                    style={{ width: '100%', maxHeight: '360px', objectFit: 'contain', display: 'block', margin: '0 auto', background: 'var(--bg-inset-80)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}
                  />
                </a>
              </div>
            )}

            {/* Photos */}
            {photoArtifacts.length > 0 && (
              <div>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Camera size={16} />
                  <span>Photos ({photoArtifacts.length})</span>
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '0.75rem' }}>
                  {photoArtifacts.map((photo, idx) => {
                    if (!photo.id) return null;
                    const photoUrl = getArtifactFileUrl(photo.id);
                    const isGauge = photo.category === 'gauge';
                    const isPipe = photo.category === 'pipe';
                    return (
                      <a
                        key={idx}
                        href={photoUrl}
                        target="_blank"
                        rel="noreferrer"
                        style={{ position: 'relative', display: 'block', height: '130px', borderRadius: 'var(--radius-md)', overflow: 'hidden', border: '1px solid var(--border-color)', background: 'var(--bg-inset-80)' }}
                      >
                        <img src={photoUrl} alt={photo.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
                        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'var(--bg-inset-85)', padding: '3px 6px', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          {isGauge ? <Gauge size={11} color="var(--accent-cyan)" /> : isPipe ? <Pipette size={11} color="var(--accent-cyan)" /> : null}
                          <span style={{ fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                            {isGauge ? 'Gauge' : isPipe ? 'Pipe' : 'Photo'}
                          </span>
                        </div>
                      </a>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Downloadable files */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                  Files ({artifacts.length})
                </h3>
                {artifacts.length > 0 && (
                  <a
                    href={getRevisionZipUrl(test.log_no, rev.revision_id)}
                    className="btn-primary"
                    download
                    style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
                  >
                    <Download size={14} />
                    <span>Download All (ZIP)</span>
                  </a>
                )}
              </div>

              {artifacts.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>No files attached yet.</div>
              ) : (
                <div className="artifacts-grid">
                  {[...(graphArtifact ? [graphArtifact] : []), ...otherArtifacts, ...photoArtifacts].map((art, idx) => {
                    if (!art.id) return null;
                    const fileUrl = getArtifactFileUrl(art.id);
                    return (
                      <a key={idx} href={fileUrl} download={art.name} className="artifact-card" title={`Download ${art.name}`}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden' }}>
                          {getArtifactIcon(art.file_type)}
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{art.name}</div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{(art.size_bytes / 1024).toFixed(1)} KB</div>
                          </div>
                        </div>
                        <Download size={16} color="var(--text-muted)" />
                      </a>
                    );
                  })}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.78rem', justifyContent: 'center', padding: '0.5rem 0' }}>
              <AlertCircle size={13} />
              <span>This is a view-only link. Data can only be edited inside the ARDOR application.</span>
            </div>
          </>
        )}
      </main>
    </div>
  );
};
