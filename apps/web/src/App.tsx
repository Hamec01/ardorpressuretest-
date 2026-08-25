import React, { useEffect, useState, useMemo } from 'react';
import { Header } from './components/Header';
import { SearchFilters } from './components/SearchFilters';
import { TestCard } from './components/TestCard';
import { TestTableView } from './components/TestTableView';
import { TestDetailModal } from './components/TestDetailModal';
import { NewTestModal } from './components/NewTestModal';
import { LoginModal } from './components/LoginModal';
import { AuditLogModal } from './components/AuditLogModal';
import { RecordsTab } from './components/RecordsTab';
import { NewRecordModal } from './components/NewRecordModal';
import { RecordDetailModal } from './components/RecordDetailModal';
import { FaqTab } from './components/FaqTab';
import { fetchPressureTests, fetchTrash } from './api';
import { PressureTest, PressureTestRecord } from './types';
import { useI18n } from './context/LanguageContext';
import { RefreshCw, Inbox, AlertCircle, Layers, FileSpreadsheet, HelpCircle, Trash2 } from 'lucide-react';

export const App: React.FC = () => {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<'tests' | 'trash' | 'records' | 'faq'>('tests');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  const [tests, setTests] = useState<PressureTest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [selectedTest, setSelectedTest] = useState<PressureTest | null>(null);
  const [isNewTestOpen, setIsNewTestOpen] = useState<boolean>(false);
  const [isLoginOpen, setIsLoginOpen] = useState<boolean>(false);
  const [isAuditOpen, setIsAuditOpen] = useState<boolean>(false);

  // PTR State
  const [selectedRecord, setSelectedRecord] = useState<PressureTestRecord | null>(null);
  const [isNewRecordOpen, setIsNewRecordOpen] = useState<boolean>(false);
  const [recordsRefreshKey, setRecordsRefreshKey] = useState<number>(0);

  const loadData = async (query?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = activeTab === 'trash' ? await fetchTrash() : await fetchPressureTests(query);
      setTests(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load test data from local server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'tests' || activeTab === 'trash') {
      const timer = setTimeout(() => {
        loadData(searchQuery);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [searchQuery, activeTab]);

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
        {/* Navigation Tabs (3 Tabs: Tests, PTR, FAQ) */}
        <div style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid var(--border-color)', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <button
            onClick={() => setActiveTab('tests')}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'tests' ? '2px solid var(--accent-cyan)' : '2px solid transparent',
              color: activeTab === 'tests' ? 'var(--text-primary)' : 'var(--text-muted)',
              padding: '0.6rem 1rem',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <Layers size={16} color={activeTab === 'tests' ? 'var(--accent-cyan)' : 'inherit'} />
            <span>{t('tab_tests')}</span>
          </button>

          <button
            onClick={() => setActiveTab('records')}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'records' ? '2px solid var(--accent-amber)' : '2px solid transparent',
              color: activeTab === 'records' ? 'var(--text-primary)' : 'var(--text-muted)',
              padding: '0.6rem 1rem',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <FileSpreadsheet size={16} color={activeTab === 'records' ? 'var(--accent-amber)' : 'inherit'} />
            <span>{t('tab_records')}</span>
          </button>

          <button
            onClick={() => setActiveTab('faq')}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === 'faq' ? '2px solid var(--accent-emerald)' : '2px solid transparent',
              color: activeTab === 'faq' ? 'var(--text-primary)' : 'var(--text-muted)',
              padding: '0.6rem 1rem',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <HelpCircle size={16} color={activeTab === 'faq' ? 'var(--accent-emerald)' : 'inherit'} />
            <span>{t('tab_faq')}</span>
          </button>

            <button
              type="button"
              onClick={() => setActiveTab('trash')}
              aria-label="Открыть корзину"
              title="Корзина, хранение 14 дней"
              style={{
                background: activeTab === 'trash' ? 'rgba(244, 63, 94, 0.12)' : 'transparent',
                border: 'none',
                borderBottom: activeTab === 'trash' ? '2px solid var(--accent-rose)' : '2px solid transparent',
                color: activeTab === 'trash' ? 'var(--accent-rose)' : 'var(--text-muted)',
                padding: '0.6rem 0.75rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Trash2 size={17} />
            </button>
        </div>

        {error && (
          <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid var(--accent-rose)', color: '#FECDD3', padding: '1rem', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <AlertCircle size={20} color="var(--accent-rose)" />
            <span>{error}</span>
          </div>
        )}

          {activeTab === 'tests' || activeTab === 'trash' ? (
          <>
              {activeTab === 'tests' && <SearchFilters query={searchQuery} onQueryChange={setSearchQuery} activeFilter={activeFilter} onFilterSelect={setActiveFilter} viewMode={viewMode} onViewModeChange={setViewMode} />}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', marginTop: '-0.5rem' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Showing <strong>{filteredTests.length}</strong> of {tests.length} pressure tests
              </div>

              <button
                onClick={() => loadData(searchQuery)}
                style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-md)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
              >
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                <span>{t('btn_refresh')}</span>
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
                  {t('no_tests_title')}
                </div>
                <p>{t('no_tests_desc')}</p>
              </div>
            ) : viewMode === 'table' ? (
              <TestTableView
                tests={filteredTests}
                onSelectTest={(t) => setSelectedTest(t)}
              />
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
          </>
        ) : activeTab === 'records' ? (
          <RecordsTab
            refreshTrigger={recordsRefreshKey}
            onSelectRecord={(rec) => setSelectedRecord(rec)}
            onNewRecordClick={() => setIsNewRecordOpen(true)}
          />
        ) : (
          <FaqTab />
        )}
      </main>

      {selectedTest && (
        <TestDetailModal
          test={selectedTest}
          onClose={() => setSelectedTest(null)}
          onUpdate={(updated) => {
            setSelectedTest(updated);
            loadData(searchQuery);
          }}
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

      {selectedRecord && (
        <RecordDetailModal
          record={selectedRecord}
          onClose={() => setSelectedRecord(null)}
          onUpdate={() => {
            setRecordsRefreshKey(k => k + 1);
          }}
        />
      )}

      {isNewRecordOpen && (
        <NewRecordModal
          onClose={() => setIsNewRecordOpen(false)}
          onSuccess={(created) => {
            setIsNewRecordOpen(false);
            setRecordsRefreshKey(k => k + 1);
            setSelectedRecord(created);
          }}
        />
      )}
    </div>
  );
};
