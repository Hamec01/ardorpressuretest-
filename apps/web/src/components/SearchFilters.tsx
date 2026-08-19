import React from 'react';
import { Search, X, LayoutGrid, List } from 'lucide-react';

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
  return (
    <div className="search-section">
      <div className="search-input-wrapper">
        <Search className="search-icon" size={22} />
        <input
          type="text"
          className="search-input"
          placeholder="Search by Log No. (e.g. 014FED), Pipe No. (e.g. 122153/41), Bundle, Operator or Project..."
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          autoFocus
        />
        {query && (
          <button className="search-clear-btn" onClick={() => onQueryChange('')} title="Clear search">
            <X size={18} />
          </button>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div className="filter-pills">
          <button
            className={`filter-pill ${activeFilter === 'all' ? 'active' : ''}`}
            onClick={() => onFilterSelect('all')}
          >
            All Tests
          </button>
          <button
            className={`filter-pill ${activeFilter === 'complete' ? 'active' : ''}`}
            onClick={() => onFilterSelect('complete')}
          >
            Complete Revisions
          </button>
          <button
            className={`filter-pill ${activeFilter === 'recent' ? 'active' : ''}`}
            onClick={() => onFilterSelect('recent')}
          >
            Recent (24h)
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
              title="Плитка (Grid view with photo thumbnails)"
            >
              <LayoutGrid size={15} />
              <span>Карточки</span>
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
              title="Таблица / Список (Compact table view)"
            >
              <List size={15} />
              <span>Таблица</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
