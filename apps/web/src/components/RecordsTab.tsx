import React, { useState, useEffect } from 'react';
import { PressureTestRecord } from '../types';
import { fetchRecords, getRecordPdfUrl } from '../api';
import { Plus, Download, User, Search, RefreshCw, FileSpreadsheet, ShieldCheck } from 'lucide-react';

interface RecordsTabProps {
  onSelectRecord: (rec: PressureTestRecord) => void;
  onNewRecordClick: () => void;
}

export const RecordsTab: React.FC<RecordsTabProps> = ({ onSelectRecord, onNewRecordClick }) => {
  const [records, setRecords] = useState<PressureTestRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const loadRecords = async () => {
    try {
      setLoading(true);
      const data = await fetchRecords(search, statusFilter);
      setRecords(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      loadRecords();
    }, 200);
    return () => clearTimeout(timer);
  }, [search, statusFilter]);

  return (
    <div>
      {/* Top Banner / Explanation */}
      <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', padding: '0.9rem 1.25rem', borderRadius: 'var(--radius-md)', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <FileSpreadsheet size={24} color="var(--accent-amber)" />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--accent-amber)' }}>
              ARDOR Pressure Test Records (PTR Blanks)
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Сводные официальные протоколы испытаний со списком труб, выдержкой давления, росписью прораба и цифровым штампом верификации.
            </div>
          </div>
        </div>

        <button
          className="btn-primary"
          onClick={onNewRecordClick}
          style={{ background: 'var(--accent-amber)', color: '#0F172A', fontWeight: 700, padding: '0.5rem 1.1rem', fontSize: '0.85rem' }}
        >
          <Plus size={16} />
          <span>+ Создать протокол (New PTR)</span>
        </button>
      </div>

      {/* Search & Actions Bar */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flex: 1, minWidth: '280px', alignItems: 'center' }}>
          <div className="search-input-wrapper" style={{ flex: 1 }}>
            <Search size={18} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Поиск по номеру акта (PTR-2026-001), проекту, системе или прорабу..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="filter-pills" style={{ marginTop: 0 }}>
            <button className={`filter-pill ${statusFilter === 'all' ? 'active' : ''}`} onClick={() => setStatusFilter('all')}>Все</button>
            <button className={`filter-pill ${statusFilter === 'draft' ? 'active' : ''}`} onClick={() => setStatusFilter('draft')}>Черновики (Draft)</button>
            <button className={`filter-pill ${statusFilter === 'confirmed' ? 'active' : ''}`} onClick={() => setStatusFilter('confirmed')}>Подписанные (Confirmed)</button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={loadRecords}
            style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.45rem 0.85rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Обновить</span>
          </button>

          <button className="btn-primary" onClick={onNewRecordClick} style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}>
            <Plus size={16} />
            <span>Новый протокол</span>
          </button>
        </div>
      </div>

      {/* Grid or Empty State */}
      {loading ? (
        <div className="empty-state">Загрузка документов Pressure Test Record...</div>
      ) : records.length === 0 ? (
        <div className="empty-state" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
          <FileSpreadsheet size={56} color="var(--accent-amber)" style={{ opacity: 0.7, marginBottom: '1rem' }} />
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            Пока нет созданных протоколов PTR
          </div>
          <p style={{ maxWidth: '540px', margin: '0 auto 1.5rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Протокол Pressure Test Record позволяет объединить несколько труб в один официальный акт опрессовки ARDOR, завизировать его электронной росписью прораба и сформировать утверждённый PDF с QR-штампом.
          </p>
          <button
            className="btn-primary"
            onClick={onNewRecordClick}
            style={{ margin: '0 auto', padding: '0.65rem 1.4rem', fontSize: '0.95rem' }}
          >
            <Plus size={18} />
            <span>Создать первый протокол (Create First PTR)</span>
          </button>
        </div>
      ) : (
        <div className="cards-grid">
          {records.map((rec) => {
            const isConfirmed = rec.status === 'confirmed' || rec.status === 'signed';
            return (
              <div key={rec.id} className="test-card" onClick={() => onSelectRecord(rec)} style={{ borderLeft: isConfirmed ? '4px solid var(--accent-emerald)' : '4px solid var(--accent-amber)' }}>
                <div>
                  <div className="card-top">
                    <div>
                      <div className="log-number" style={{ color: 'var(--accent-amber)' }}>{rec.record_number}</div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                        {rec.system} — {rec.project}
                      </div>
                    </div>
                    <span className={`status-badge ${rec.status}`}>
                      {rec.status}
                    </span>
                  </div>

                  <div className="metrics-row">
                    <div className="metric-item">
                      <span className="metric-label">MEDIUM</span>
                      <span className="metric-val">{rec.test_medium}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">TEST PRESSURE</span>
                      <span className="metric-val">{rec.test_pressure || 'N/A'}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">ITEMS</span>
                      <span className="metric-val">{rec.items?.length || 0} pipes</span>
                    </div>
                  </div>

                  {rec.items && rec.items.length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Pipes tested:</div>
                      <div className="tag-list">
                        {rec.items.slice(0, 3).map((it, idx) => (
                          <span key={idx} className="tag-pipe">{it.pipe_number}</span>
                        ))}
                        {rec.items.length > 3 && <span className="tag-pipe">+{rec.items.length - 3} more</span>}
                      </div>
                    </div>
                  )}

                  {isConfirmed && rec.verification_code && (
                    <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--accent-emerald)', fontSize: '0.75rem', fontWeight: 600 }}>
                      <ShieldCheck size={14} />
                      <span>Verified: {rec.verification_code}</span>
                    </div>
                  )}
                </div>

                <div className="card-footer">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <User size={14} />
                    <span>Foreman: {rec.foreman_name || 'N/A'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <a
                      href={getRecordPdfUrl(rec.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="filter-pill"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}
                      download
                      title="Download Official PDF Blank"
                    >
                      <Download size={12} />
                      <span>PDF Blank</span>
                    </a>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
