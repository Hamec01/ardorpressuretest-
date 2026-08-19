import React, { useState } from 'react';
import { X, Plus, Trash2, Check, AlertCircle, FileText } from 'lucide-react';
import { PressureTestRecord, RecordItem } from '../types';
import { useAuth } from '../context/AuthContext';

interface NewRecordModalProps {
  onClose: () => void;
  onSuccess: (created: PressureTestRecord) => void;
}

export const NewRecordModal: React.FC<NewRecordModalProps> = ({ onClose, onSuccess }) => {
  const { user, token } = useAuth();
  const [recordNumber, setRecordNumber] = useState<string>(`PTR-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 900) + 100)}`);
  const [project, setProject] = useState<string>('Meyer Turku NB-1400');
  const [system, setSystem] = useState<string>('Main Fuel Gas Line');
  const [insNo, setInsNo] = useState<string>('INS-2026-001');
  const [testDate, setTestDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [testMedium, setTestMedium] = useState<string>('Water');
  const [testPressure, setTestPressure] = useState<string>('15.0 bar');
  const [designPressure, setDesignPressure] = useState<string>('10.0 bar');
  const [durationMin, setDurationMin] = useState<string>('60 min');
  const [foremanName, setForemanName] = useState<string>(user?.full_name || 'Matti Meikäläinen');
  const [qcInspector, setQcInspector] = useState<string>('Jari Korhonen');
  const [clientSurveyor, setClientSurveyor] = useState<string>('DNV Inspector');
  const [notes, setNotes] = useState<string>('Pressure hold test completed successfully under normal ambient temperature.');

  const [items, setItems] = useState<RecordItem[]>([
    { item_no: 1, pipe_number: 'P-101', drawing_no: 'DWG-01-A', spool_no: 'SP-01', log_no: '014FED', hold_start_bar: '15.2', hold_end_bar: '15.1', result: 'PASS', notes: 'OK' },
    { item_no: 2, pipe_number: 'P-102', drawing_no: 'DWG-01-A', spool_no: 'SP-02', log_no: '014FED', hold_start_bar: '15.2', hold_end_bar: '15.1', result: 'PASS', notes: 'OK' },
  ]);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const addItemRow = () => {
    setItems([
      ...items,
      {
        item_no: items.length + 1,
        pipe_number: `P-${100 + items.length + 1}`,
        drawing_no: 'DWG-01-A',
        spool_no: '',
        log_no: '014FED',
        hold_start_bar: '15.2',
        hold_end_bar: '15.1',
        result: 'PASS',
        notes: ''
      }
    ]);
  };

  const removeItemRow = (idx: number) => {
    const updated = items.filter((_, i) => i !== idx).map((it, i) => ({ ...it, item_no: i + 1 }));
    setItems(updated);
  };

  const updateItemField = (idx: number, field: keyof RecordItem, val: any) => {
    const updated = [...items];
    updated[idx] = { ...updated[idx], [field]: val };
    setItems(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const payload = {
        record_number: recordNumber.trim(),
        project: project.trim(),
        system: system.trim(),
        ins_no: insNo.trim(),
        test_date: testDate,
        test_medium: testMedium,
        test_pressure: testPressure,
        design_pressure: designPressure,
        duration_min: durationMin,
        foreman_name: foremanName,
        qc_inspector: qcInspector,
        client_surveyor: clientSurveyor,
        notes: notes,
        items: items
      };

      const res = await fetch('/api/v1/records', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Failed to create record (${res.status})`);
      }

      const created = await res.json();
      onSuccess(created);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create record.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '900px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <FileText size={20} color="var(--accent-amber)" />
            <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>New Pressure Test Record (PTR)</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} disabled={isSubmitting}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: '1.25rem' }}>
          {errorMsg && (
            <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '0.75rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <AlertCircle size={16} color="var(--accent-rose)" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Section 1: General Info */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--accent-amber)' }}>
              1. Document & System Information
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Record Number *</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={recordNumber} onChange={(e) => setRecordNumber(e.target.value)} required />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Project Name</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={project} onChange={(e) => setProject(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>System / Line</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={system} onChange={(e) => setSystem(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Inspection No.</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={insNo} onChange={(e) => setInsNo(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Test Date</label>
                <input type="date" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={testDate} onChange={(e) => setTestDate(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Test Medium</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={testMedium} onChange={(e) => setTestMedium(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Target Test Pressure</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={testPressure} onChange={(e) => setTestPressure(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Design Pressure</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={designPressure} onChange={(e) => setDesignPressure(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Min Hold Duration</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={durationMin} onChange={(e) => setDurationMin(e.target.value)} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>General Notes</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={notes} onChange={(e) => setNotes(e.target.value)} />
              </div>
            </div>
          </div>

          {/* Section 2: Items Table */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-amber)' }}>
                2. Tested Pipeline Elements ({items.length} rows)
              </div>
              <button type="button" onClick={addItemRow} className="filter-pill" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem' }}>
                <Plus size={13} />
                <span>Add Pipe Row</span>
              </button>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                    <th style={{ padding: '0.4rem', textAlign: 'center', width: '35px' }}>#</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Pipe Number *</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Dwg / Spool</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Log No</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left', width: '80px' }}>Start bar</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left', width: '80px' }}>End bar</th>
                    <th style={{ padding: '0.4rem', textAlign: 'center', width: '85px' }}>Result</th>
                    <th style={{ padding: '0.4rem', width: '35px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                      <td style={{ padding: '0.4rem', textAlign: 'center', color: 'var(--text-muted)' }}>{it.item_no}</td>
                      <td style={{ padding: '0.3rem' }}>
                        <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.4rem', fontSize: '0.8rem' }} value={it.pipe_number} onChange={(e) => updateItemField(idx, 'pipe_number', e.target.value)} required />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.4rem', fontSize: '0.8rem' }} value={it.drawing_no || ''} onChange={(e) => updateItemField(idx, 'drawing_no', e.target.value)} placeholder="DWG-01" />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.4rem', fontSize: '0.8rem' }} value={it.log_no || ''} onChange={(e) => updateItemField(idx, 'log_no', e.target.value)} placeholder="014FED" />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.4rem', fontSize: '0.8rem' }} value={it.hold_start_bar || ''} onChange={(e) => updateItemField(idx, 'hold_start_bar', e.target.value)} />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.4rem', fontSize: '0.8rem' }} value={it.hold_end_bar || ''} onChange={(e) => updateItemField(idx, 'hold_end_bar', e.target.value)} />
                      </td>
                      <td style={{ padding: '0.3rem', textAlign: 'center' }}>
                        <select
                          value={it.result}
                          onChange={(e) => updateItemField(idx, 'result', e.target.value)}
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: it.result === 'PASS' ? 'var(--accent-emerald)' : 'var(--accent-rose)', borderRadius: 'var(--radius-sm)', padding: '0.25rem', fontSize: '0.75rem', fontWeight: 600 }}
                        >
                          <option value="PASS">PASS</option>
                          <option value="FAIL">FAIL</option>
                          <option value="PENDING">PENDING</option>
                        </select>
                      </td>
                      <td style={{ padding: '0.3rem', textAlign: 'center' }}>
                        {items.length > 1 && (
                          <button type="button" onClick={() => removeItemRow(idx)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer' }}>
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 3: Signatures */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--accent-amber)' }}>
              3. Verification & Signatures
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Foreman Name</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={foremanName} onChange={(e) => setForemanName(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>QC Inspector Name</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={qcInspector} onChange={(e) => setQcInspector(e.target.value)} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Client / Surveyor Name</label>
                <input type="text" className="search-input" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} value={clientSurveyor} onChange={(e) => setClientSurveyor(e.target.value)} />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }} disabled={isSubmitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              <Check size={16} />
              <span>{isSubmitting ? 'Saving Record...' : 'Save & Generate Official Blank'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
