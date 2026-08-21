import React from 'react';
import { Search, X, LayoutGrid, List } from 'lucide-react';
import { useI18n } from '../context/LanguageContext';

interface SearchFiltersProps {
  query: string;
  onQueryChange: (q: string) => void;
  activeFilter: string;
  onFilterSelect: (filter: string) => void;
  viewMode?: 'grid' | 'table';
  onViewModeChange?: (mode: 'grid' | 'table') => void;
}

export const SearchFilters: React.FC<SearchFiltersProps> = ({
  query,
  onQueryChange,
  activeFilter,
  onFilterSelect,
  viewMode = 'grid',
  onViewModeChange
}) => {
  const { t } = useI18n();

  return (
    <div className="search-section">
      <div className="search-input-wrapper">
        <Search className="search-icon" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder={t('search_placeholder')}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          autoFocus
        />
        {query && (
          <button className="search-clear-btn" onClick={() => onQueryChange('')} title="Clear search">
            <X size={16} />
          </button>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div className="filter-pills">
          <button
            className={`filter-pill ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => onFilterSelect('all')}
          >
            {t('filter_all')}
          </button>
          <button
            className={`filter-pill ${activeFilter === 'complete' ? 'active' : ''}`}
            onClick={() => onFilterSelect('complete')}
          >
            {t('filter_complete')}
          </button>
          <button
            className={`filter-pill ${activeFilter === 'recent' ? 'active' : ''}`}
            onClick={() => onFilterSelect('recent')}
          >
            Recent (24h)
          </button>
          <button
            className={`filter-pill ${activeFilter === 'pipecloud_added' ? 'active' : ''}`}
            onClick={() => onFilterSelect('pipecloud_added')}
            style={{ borderColor: activeFilter === 'pipecloud_added' ? '#10b981' : undefined }}
          >
            ☁ {t('pipecloud_filter_added')}
          </button>
          <button
            className={`filter-pill ${activeFilter === 'pipecloud_not_added' ? 'active' : ''}`}
            onClick={() => onFilterSelect('pipecloud_not_added')}
            style={{ borderColor: activeFilter === 'pipecloud_not_added' ? '#f87171' : undefined }}
          >
            ☁ {t('pipecloud_filter_not_added')}
          </button>
        </div>

        {/* View Mode Toggle: Grid vs Table */}
        {onViewModeChange && (
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '3px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => onViewModeChange('grid')}
              style={{
                background: viewMode === 'grid' ? 'var(--accent-cyan)' : 'transparent',
                color: viewMode === 'grid' ? '#0F172A' : 'var(--text-muted)',
                border: 'none',
                padding: '0.35rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                transition: 'all 0.2s ease'
              }}
              title="Cards / Grid view"
            >
              <LayoutGrid size={15} />
              <span>{t('view_grid')}</span>
            </button>

            <button
              type="button"
              onClick={() => onViewModeChange('table')}
              style={{
                background: viewMode === 'table' ? 'var(--accent-cyan)' : 'transparent',
                color: viewMode === 'table' ? '#0F172A' : 'var(--text-muted)',
                border: 'none',
                padding: '0.35rem 0.65rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                transition: 'all 0.2s ease'
              }}
              title="Table / List view"
            >
              <List size={15} />
              <span>{t('view_table')}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
