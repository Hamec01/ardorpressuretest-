import React, { useState } from 'react';
import { PressureTest, TestRevision } from '../types';
import { getRevisionZipUrl } from '../api';
import { X, Download, FileText, Image as ImageIcon, FileSpreadsheet, FileCode, CheckCircle2, Copy } from 'lucide-react';

interface TestDetailModalProps {
  test: PressureTest;
  onClose: () => void;
}

export const TestDetailModal: React.FC<TestDetailModalProps> = ({ test, onClose }) => {
  const [selectedRevIndex, setSelectedRevIndex] = useState<number>(0);
  const [copiedSha, setCopiedSha] = useState<string | null>(null);

  const revisions = test.revisions || [];
  const currentRev: TestRevision | undefined = revisions[selectedRevIndex] || revisions[0];

  const meta = currentRev?.metadata_json || {};
  const metrics = currentRev?.metrics_json || {};
  const artifacts = currentRev?.artifacts || [];

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    setTimeout(() => setCopiedSha(null), 2000);
  };

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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="log-number" style={{ fontSize: '1.4rem' }}>Log {test.log_no}</span>
              <span className={`status-badge ${currentRev?.status || 'complete'}`}>
                {currentRev?.status || 'complete'}
              </span>
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              {meta.system || 'Industrial Pipeline Test'} — {meta.project || 'Project ARDOR'}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {currentRev && (
              <a
                href={getRevisionZipUrl(test.log_no, currentRev.revision_id)}
                className="btn-primary"
                download
              >
                <Download size={16} />
                <span>Download ZIP Package</span>
              </a>
            )}
            <button className="modal-close-btn" onClick={onClose}>
              <X size={22} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Revision Switcher if multiple */}
          {revisions.length > 1 && (
            <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
                REVISION HISTORY ({revisions.length} revisions):
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {revisions.map((rev, idx) => (
                  <button
                    key={rev.id}
                    className={`filter-pill ${selectedRevIndex === idx ? 'active' : ''}`}
                    onClick={() => setSelectedRevIndex(idx)}
                  >
                    Rev {rev.revision_id} {rev.is_primary ? '(Primary)' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Key Metrics */}
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Inspection & Pressure Metrics
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST PRESSURE</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  {meta.test_pressure || 'N/A'}
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MIN / MAX RECORDED</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                  {metrics.min_pressure_bar != null ? `${metrics.min_pressure_bar.toFixed(2)} / ${metrics.max_pressure_bar?.toFixed(2)} bar` : 'N/A'}
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>TEST DURATION</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 700 }}>
                  {metrics.duration_formatted || '00:00:00'}
                </div>
              </div>

              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EVALUATION PROPOSAL</div>
                <div style={{ fontWeight: 700, color: metrics.evaluation_status === 'PASS' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                  {metrics.evaluation_status || 'Not Evaluated'}
                </div>
              </div>
            </div>
          </div>

          {/* Traceability Metadata */}
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Traceability & Pipe Identifiers
            </h3>
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Operator: </span>
                  <strong>{currentRev?.operator || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Inspection No: </span>
                  <strong>{meta.ins_no || 'N/A'}</strong>
                </div>
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>WIKA Gauge Serial: </span>
                  <strong>{meta.wika_nr || 'N/A'}</strong>
                </div>
              </div>

              {meta.pipe_numbers && meta.pipe_numbers.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                    Pipe Numbers ({meta.pipe_numbers.length}):
                  </div>
                  <div className="tag-list">
                    {meta.pipe_numbers.map((p: string, i: number) => (
                      <span key={i} className="tag-pipe" style={{ fontSize: '0.85rem', padding: '0.2rem 0.6rem' }}>
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Artifacts & Provenance */}
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
              Revision Evidence Artifacts ({artifacts.length})
            </h3>
            <div className="artifacts-grid">
              {artifacts.map((art, idx) => (
                <div key={idx} className="artifact-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                    {getArtifactIcon(art.file_type)}
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{art.name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {(art.size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleCopySha(art.sha256)}
                    style={{ background: 'transparent', border: 'none', color: copiedSha === art.sha256 ? 'var(--accent-emerald)' : 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                    title={`Copy SHA-256: ${art.sha256}`}
                  >
                    {copiedSha === art.sha256 ? <CheckCircle2 size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
