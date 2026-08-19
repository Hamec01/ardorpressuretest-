import React, { useState } from 'react';
import { X, Plus, Trash2, Check, AlertCircle, FileSpreadsheet } from 'lucide-react';
import { PressureTestRecord, RecordItem } from '../types';
import { useAuth } from '../context/AuthContext';

interface NewRecordModalProps {
  onClose: () => void;
  onSuccess: (created: PressureTestRecord) => void;
}

export const NewRecordModal: React.FC<NewRecordModalProps> = ({ onClose, onSuccess }) => {
  const { token } = useAuth();

  // Document Fields matching official ARDOR PAINEKOEPÖYTÄKIRJA
  const [recordNumber, setRecordNumber] = useState<string>('NB1402PM-13388');
  const [insNo, setInsNo] = useState<string>('Inspection 044');
  const [jobNo, setJobNo] = useState<string>('NB402');
  const [project, setProject] = useState<string>('ICON3 LNG PF inspection');
  const [designPressure, setDesignPressure] = useState<string>('16');
  const [testPressure, setTestPressure] = useState<string>('24');
  const [wikaNr, setWikaNr] = useState<string>('1A01JFDQ12E');
  const [testMedium, setTestMedium] = useState<string>('Water');
  const [durationMin] = useState<string>('60 min');
  const [foremanName, setForemanName] = useState<string>('DE LUCA');
  const [notes, setNotes] = useState<string>('Hold test completed. No pressure drops detected. Test passed successfully.');

  // Table rows matching Drawing No, System, Part No, Date, Duration, Log No
  const [items, setItems] = useState<RecordItem[]>([
    {
      item_no: 1,
      drawing_no: 'D.1402.006D.0006C.725.117_C',
      spool_no: '64722P1201',
      pipe_number: '1001C',
      log_no: '044-1',
      hold_start_bar: '24.0',
      hold_end_bar: '24.0',
      result: 'PASS',
      notes: '60 min'
    },
    {
      item_no: 2,
      drawing_no: 'D.1402.006D.0006D.725.117_C',
      spool_no: '64722P1201',
      pipe_number: '1001C',
      log_no: '044-1',
      hold_start_bar: '24.0',
      hold_end_bar: '24.0',
      result: 'PASS',
      notes: '60 min'
    },
    {
      item_no: 3,
      drawing_no: 'D.1402.005D.00WT8.775.117_A',
      spool_no: '64722P1201',
      pipe_number: '1002',
      log_no: '044-1',
      hold_start_bar: '24.0',
      hold_end_bar: '24.0',
      result: 'PASS',
      notes: '60 min'
    },
    {
      item_no: 4,
      drawing_no: 'D.1402.005D.00WT8.775.117_A',
      spool_no: '64722P1105',
      pipe_number: '1003',
      log_no: '044-1',
      hold_start_bar: '24.0',
      hold_end_bar: '24.0',
      result: 'PASS',
      notes: '60 min'
    }
  ]);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const addItemRow = () => {
    setItems([
      ...items,
      {
        item_no: items.length + 1,
        drawing_no: 'D.1402.005D.00WT8.775.117_A',
        spool_no: '64722P1201',
        pipe_number: `100${items.length + 1}`,
        log_no: '044-1',
        hold_start_bar: testPressure,
        hold_end_bar: testPressure,
        result: 'PASS',
        notes: durationMin
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
        system: jobNo.trim(),
        ins_no: insNo.trim(),
        test_date: new Date().toISOString().split('T')[0],
        test_medium: testMedium,
        test_pressure: testPressure,
        design_pressure: designPressure,
        duration_min: durationMin,
        foreman_name: foremanName.trim(),
        qc_inspector: 'Inspector',
        client_surveyor: 'Witnessed / Reviewed',
        notes: notes,
        items: items
      };

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch('/api/v1/records', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Ошибка создания протокола (${res.status})`);
      }

      const created = await res.json();
      onSuccess(created);
    } catch (err: any) {
      setErrorMsg(err.message || 'Не удалось сохранить протокол.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '980px', width: '94vw' }} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <FileSpreadsheet size={22} color="var(--accent-amber)" />
            <div>
              <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                PAINEKOEPÖYTÄKIRJA / PRESSURE TEST RECORD
              </span>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Официальный протокол опрессовки ARDOR
              </div>
            </div>
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

          {/* Section 1: Header Metadata Grid matching ARDOR Form */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Numero tai tunnus / Number or mark *
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={insNo}
                  onChange={(e) => setInsNo(e.target.value)}
                  placeholder="Inspection 044"
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Record / Document Number *
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={recordNumber}
                  onChange={(e) => setRecordNumber(e.target.value)}
                  placeholder="NB1402PM-13388"
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Työnumero / Job No
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={jobNo}
                  onChange={(e) => setJobNo(e.target.value)}
                  placeholder="NB402"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Projektin nro tai nimi / Project No or name
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  placeholder="ICON3 LNG PF inspection"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Suunnittelupaine / Design pressure (bar)
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={designPressure}
                  onChange={(e) => setDesignPressure(e.target.value)}
                  placeholder="16"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Koepaine / Test pressure (bar)
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={testPressure}
                  onChange={(e) => setTestPressure(e.target.value)}
                  placeholder="24"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Mittarin nro / WIKA S#
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={wikaNr}
                  onChange={(e) => setWikaNr(e.target.value)}
                  placeholder="1A01JFDQ12E"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Testiaine / Test material
                </label>
                <select
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={testMedium}
                  onChange={(e) => setTestMedium(e.target.value)}
                >
                  <option value="Water">Vesi / Water</option>
                  <option value="Air">Ilma / Air</option>
                  <option value="Glycol">Glykoli / Glycol</option>
                  <option value="Nitrogen">Typpi / Nitrogen</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Items Table (Piirustus nro, Systeemi, Osa nro, Pvm, Kesto, Log nro) */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-amber)' }}>
                Таблица опрессованных элементов ({items.length} строк)
              </div>
              <button type="button" onClick={addItemRow} className="filter-pill" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                <Plus size={14} />
                <span>+ Добавить строку (Add Row)</span>
              </button>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    <th style={{ padding: '0.4rem', textAlign: 'center', width: '30px' }}>#</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left' }}>Piirustus nro (Drawing No) *</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left', width: '140px' }}>Systeemi (System)</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left', width: '110px' }}>Osa nro (Part No)</th>
                    <th style={{ padding: '0.4rem', textAlign: 'left', width: '100px' }}>Log nro</th>
                    <th style={{ padding: '0.4rem', textAlign: 'center', width: '80px' }}>Tulos (Result)</th>
                    <th style={{ padding: '0.4rem', width: '35px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                      <td style={{ padding: '0.4rem', textAlign: 'center', color: 'var(--text-muted)' }}>{it.item_no}</td>
                      <td style={{ padding: '0.3rem' }}>
                        <input
                          type="text"
                          className="search-input"
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.5rem', fontSize: '0.85rem' }}
                          value={it.drawing_no || ''}
                          onChange={(e) => updateItemField(idx, 'drawing_no', e.target.value)}
                          placeholder="D.1402.006D.0006C.725.117_C"
                          required
                        />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input
                          type="text"
                          className="search-input"
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.5rem', fontSize: '0.85rem' }}
                          value={it.spool_no || ''}
                          onChange={(e) => updateItemField(idx, 'spool_no', e.target.value)}
                          placeholder="64722P1201"
                        />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input
                          type="text"
                          className="search-input"
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.5rem', fontSize: '0.85rem' }}
                          value={it.pipe_number}
                          onChange={(e) => updateItemField(idx, 'pipe_number', e.target.value)}
                          placeholder="1001C"
                          required
                        />
                      </td>
                      <td style={{ padding: '0.3rem' }}>
                        <input
                          type="text"
                          className="search-input"
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.35rem 0.5rem', fontSize: '0.85rem' }}
                          value={it.log_no || ''}
                          onChange={(e) => updateItemField(idx, 'log_no', e.target.value)}
                          placeholder="044-1"
                        />
                      </td>
                      <td style={{ padding: '0.3rem', textAlign: 'center' }}>
                        <select
                          value={it.result}
                          onChange={(e) => updateItemField(idx, 'result', e.target.value)}
                          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: it.result === 'PASS' ? 'var(--accent-emerald)' : 'var(--accent-rose)', borderRadius: 'var(--radius-sm)', padding: '0.3rem', fontSize: '0.8rem', fontWeight: 600 }}
                        >
                          <option value="PASS">PASS</option>
                          <option value="FAIL">FAIL</option>
                        </select>
                      </td>
                      <td style={{ padding: '0.3rem', textAlign: 'center' }}>
                        {items.length > 1 && (
                          <button type="button" onClick={() => removeItemRow(idx)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer' }}>
                            <Trash2 size={15} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 3: Remarks & Signatures */}
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Witnessed / Reviewed by (Прораб / Ответственное лицо)
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={foremanName}
                  onChange={(e) => setForemanName(e.target.value)}
                  placeholder="DE LUCA"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  Huomautukset / Remarks (Примечания)
                </label>
                <input
                  type="text"
                  className="search-input"
                  style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)', padding: '0.45rem 0.65rem', fontSize: '0.9rem' }}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" onClick={onClose} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.6rem 1.2rem', borderRadius: 'var(--radius-md)', cursor: 'pointer' }} disabled={isSubmitting}>
              Отмена
            </button>
            <button type="submit" className="btn-primary" disabled={isSubmitting} style={{ padding: '0.6rem 1.4rem', fontWeight: 700 }}>
              <Check size={16} />
              <span>{isSubmitting ? 'Формирование бланка...' : 'Сформировать официальный бланк ARDOR'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
