import React, { useState, useEffect } from 'react';
import { PressureTestRecord } from '../types';
import { fetchRecords, getRecordPdfUrl } from '../api';
import { Plus, Download, User, Search, RefreshCw, Inbox } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface RecordsTabProps {
  onSelectRecord: (rec: PressureTestRecord) => void;
  onNewRecordClick: () => void;
}

export const RecordsTab: React.FC<RecordsTabProps> = ({ onSelectRecord, onNewRecordClick }) => {
  const { user } = useAuth();
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
      {/* Search & Actions Bar */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flex: 1, minWidth: '280px', alignItems: 'center' }}>
          <div className="search-input-wrapper" style={{ flex: 1 }}>
            <Search size={18} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Search by Record No (e.g. PTR-2026-001), Project, System or Foreman..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="filter-pills" style={{ marginTop: 0 }}>
            <button className={`filter-pill ${statusFilter === 'all' ? 'active' : ''}`} onClick={() => setStatusFilter('all')}>All</button>
            <button className={`filter-pill ${statusFilter === 'draft' ? 'active' : ''}`} onClick={() => setStatusFilter('draft')}>Draft</button>
            <button className={`filter-pill ${statusFilter === 'confirmed' ? 'active' : ''}`} onClick={() => setStatusFilter('confirmed')}>Confirmed</button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={loadRecords}
            style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.45rem 0.85rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          {user && (user.role === 'admin' || user.role === 'foreman') && (
            <button className="btn-primary" onClick={onNewRecordClick} style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}>
              <Plus size={16} />
              <span>Create Record</span>
            </button>
          )}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="empty-state">Loading Pressure Test Records...</div>
      ) : records.length === 0 ? (
        <div className="empty-state">
          <Inbox size={48} style={{ opacity: 0.4, marginBottom: '1rem' }} />
          <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            No Pressure Test Records found
          </div>
          <p>Create a new Pressure Test Record document or adjust search filters.</p>
        </div>
      ) : (
        <div className="cards-grid">
          {records.map((rec) => (
            <div key={rec.id} className="test-card" onClick={() => onSelectRecord(rec)}>
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
          ))}
        </div>
      )}
    </div>
  );
};
