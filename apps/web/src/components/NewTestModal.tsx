import React, { useState } from 'react';
import { X, Upload, Check, AlertCircle } from 'lucide-react';
import { PressureTest } from '../types';

interface NewTestModalProps {
  onClose: () => void;
  onSuccess: (createdTest: PressureTest) => void;
}

export const NewTestModal: React.FC<NewTestModalProps> = ({ onClose, onSuccess }) => {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [logNo, setLogNo] = useState<string>('');
  const [testPressure, setTestPressure] = useState<string>('15 bar');
  const [system, setSystem] = useState<string>('');
  const [insNo, setInsNo] = useState<string>('');
  const [project, setProject] = useState<string>('ARDOR');
  const [operator, setOperator] = useState<string>('');
  const [wikaNr, setWikaNr] = useState<string>('BG516-GDTZ-13-D');
  const [note, setNote] = useState<string>('');
  const [pipeRaw, setPipeRaw] = useState<string>('');
  const [bundleRaw, setBundleRaw] = useState<string>('');
  const [pipePhotos, setPipePhotos] = useState<File[]>([]);
  const [gaugePhotos, setGaugePhotos] = useState<File[]>([]);
  
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleCsvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setCsvFile(file);
      if (!logNo) {
        setLogNo(file.name.replace(/\.csv$/i, ''));
      }
    }
  };

  const handlePipePhotosChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setPipePhotos(Array.from(e.target.files));
    }
  };

  const handleGaugePhotosChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setGaugePhotos(Array.from(e.target.files));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      setErrorMsg('Please select a CSV measurement file.');
      return;
    }
    if (!logNo.trim()) {
      setErrorMsg('Log Number is required.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const formData = new FormData();
      formData.append('csv_file', csvFile);
      formData.append('log_no', logNo.trim());
      formData.append('test_pressure', testPressure.trim());
      formData.append('system', system.trim());
      formData.append('ins_no', insNo.trim());
      formData.append('project', project.trim());
      formData.append('operator', operator.trim());
      formData.append('wika_nr', wikaNr.trim());
      formData.append('note', note.trim());
      formData.append('pipe_numbers_raw', pipeRaw);
      formData.append('bundle_numbers_raw', bundleRaw);
      formData.append('create_pdf', 'true');

      for (const pf of pipePhotos) {
        formData.append('pipe_photos', pf);
      }
      for (const gf of gaugePhotos) {
        formData.append('gauge_photos', gf);
      }

      const res = await fetch('/api/v1/process', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Processing failed with status ${res.status}`);
      }

      const created: PressureTest = await res.json();
      onSuccess(created);
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during CSV processing.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '750px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div className="brand-logo-icon" style={{ width: '32px', height: '32px', fontSize: '1rem' }}>+</div>
            <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>New Pressure Test Wizard</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} disabled={isSubmitting}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: '1.25rem' }}>
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
              <AlertCircle size={18} color="var(--accent-rose)" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Section 1: CSV Upload */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
              1. WIKA CPG1500 CSV File *
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <label className="btn-primary" style={{ cursor: 'pointer', fontSize: '0.85rem', padding: '0.5rem 1rem' }}>
                <Upload size={16} />
                <span>Choose CSV File...</span>
                <input type="file" accept=".csv" onChange={handleCsvChange} style={{ display: 'none' }} />
              </label>
              <span style={{ fontSize: '0.85rem', color: csvFile ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {csvFile ? `Selected: ${csvFile.name} (${(csvFile.size / 1024).toFixed(1)} KB)` : 'No file selected yet'}
              </span>
            </div>
          </div>

          {/* Section 2: Metadata */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--accent-cyan)' }}>
              2. Test Metadata
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Log No. *</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. 014FED"
                  value={logNo}
                  onChange={(e) => setLogNo(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Test Pressure</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. 15 bar"
                  value={testPressure}
                  onChange={(e) => setTestPressure(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>System / Line</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. Fuel Gas System"
                  value={system}
                  onChange={(e) => setSystem(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Operator Name</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. Matti Meikäläinen"
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Inspection No.</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. INS-2026-001"
                  value={insNo}
                  onChange={(e) => setInsNo(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Project</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. ARDOR Pipeline"
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>WIKA Gauge Serial</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  value={wikaNr}
                  onChange={(e) => setWikaNr(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Notes</label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.9rem' }}
                  placeholder="e.g. Weather conditions normal"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Section 3: Pipes and Bundles */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
              3. Pipe Numbers & Bundles
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Pipe Numbers (one per line or comma-separated)
                </label>
                <textarea
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem', height: '70px', resize: 'vertical' }}
                  placeholder="P-101&#10;P-102&#10;P-103"
                  value={pipeRaw}
                  onChange={(e) => setPipeRaw(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Bundle Numbers
                </label>
                <textarea
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem', height: '70px', resize: 'vertical' }}
                  placeholder="B-01&#10;B-02"
                  value={bundleRaw}
                  onChange={(e) => setBundleRaw(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Section 4: Photo Attachments */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--accent-cyan)' }}>
              4. Evidence Photos
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Pipe Photos ({pipePhotos.length} selected)
                </label>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handlePipePhotosChange}
                  style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Gauge Photos ({gaugePhotos.length} selected)
                </label>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleGaugePhotosChange}
                  style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}
                />
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={onClose}
              style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid white', borderTopColor: 'transparent', borderRadius: '50%' }} />
                  <span>Processing CSV & Generating Artifacts...</span>
                </>
              ) : (
                <>
                  <Check size={16} />
                  <span>Process Test & Create Revision</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
