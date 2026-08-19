import React, { useEffect, useState, useMemo } from 'react';
import { Header } from './components/Header';
import { SearchFilters } from './components/SearchFilters';
import { TestCard } from './components/TestCard';
import { TestDetailModal } from './components/TestDetailModal';
import { NewTestModal } from './components/NewTestModal';
import { LoginModal } from './components/LoginModal';
import { AuditLogModal } from './components/AuditLogModal';
import { fetchPressureTests } from './api';
import { PressureTest } from './types';
import { RefreshCw, Inbox, AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  const [tests, setTests] = useState<PressureTest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [selectedTest, setSelectedTest] = useState<PressureTest | null>(null);
  const [isNewTestOpen, setIsNewTestOpen] = useState<boolean>(false);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);
  const [isAuditOpen, setIsAuditOpen] = useState<boolean>(false);

  const loadData = async (query?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPressureTests(query);
      setTests(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load test data from local server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      loadData(searchQuery);
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const filteredTests = useMemo(() => {
    if (activeFilter === 'all') return tests;
    if (activeFilter === 'complete') {
      return tests.filter(t => t.revisions.some(r => r.status === 'complete'));
    }
    if (activeFilter === 'recent') {
      const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
      return tests.filter(t => new Date(t.created_at) >= dayAgo);
    }
    return tests;
  }, [tests, activeFilter]);

  const handleTestCreated = (createdTest: PressureTest) => {
    setIsNewTestOpen(false);
    loadData(searchQuery);
    setSelectedTest(createdTest);
  };

  return (
    <div className="app-container">
      <Header
        totalCount={tests.length}
        onNewTestClick={() => setIsNewTestOpen(true)}
        onLoginClick={() => setIsLoginOpen(true)}
        onAuditClick={() => setIsAuditOpen(true)}
      />

      <main className="main-content">
        <SearchFilters
          query={searchQuery}
          onQueryChange={setSearchQuery}
          activeFilter={activeFilter}
          onFilterSelect={setActiveFilter}
        />

        {error && (
          <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <AlertCircle size={20} color="var(--accent-rose)" />
            <span>{error}</span>
          </div>
        )}

        <div className="results-header">
          <div className="results-count">
            Showing <strong>{filteredTests.length}</strong> {filteredTests.length === 1 ? 'test record' : 'test records'}
          </div>

          <button
            onClick={() => loadData(searchQuery)}
            style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        {loading ? (
          <div className="empty-state">
            <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Loading pressure test index...</div>
          </div>
        ) : filteredTests.length === 0 ? (
          <div className="empty-state">
            <Inbox size={48} style={{ opacity: 0.4, marginBottom: '1rem' }} />
            <div style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
              No matching tests found
            </div>
            <p>Try searching with another Log Number, Pipe Number, or click "+ New Test" to upload one.</p>
          </div>
        ) : (
          <div className="cards-grid">
            {filteredTests.map((test) => (
              <TestCard
                key={test.id}
                test={test}
                onSelect={(t) => setSelectedTest(t)}
              />
            ))}
          </div>
        )}
      </main>

      {selectedTest && (
        <TestDetailModal
          test={selectedTest}
          onClose={() => setSelectedTest(null)}
        />
      )}

      {isNewTestOpen && (
        <NewTestModal
          onClose={() => setIsNewTestOpen(false)}
          onSuccess={handleTestCreated}
        />
      )}

      {isLoginOpen && (
        <LoginModal
          onClose={() => setIsLoginOpen(false)}
        />
      )}

      {isAuditOpen && (
        <AuditLogModal
          onClose={() => setIsAuditOpen(false)}
        />
      )}
    </div>
  );
};
