import React from 'react';
import { Search, X, LayoutGrid, List } from 'lucide-react';
import { useI18n } from '../context/LanguageContext';
import { EMPTY_PRESSURE_TEST_FILTERS, PressureTestFilters } from '../api';

interface SearchFiltersProps {
  query: string;
  onQueryChange: (q: string) => void;
  filters: PressureTestFilters;
  onFiltersChange: (filters: PressureTestFilters) => void;
  activeFilter: string;
  onFilterSelect: (filter: string) => void;
  viewMode?: 'grid' | 'table';
  onViewModeChange?: (mode: 'grid' | 'table') => void;
}

export const SearchFilters: React.FC<SearchFiltersProps> = ({
  query,
  onQueryChange,
  filters,
  onFiltersChange,
  activeFilter,
  onFilterSelect,
  viewMode = 'grid',
  onViewModeChange
}) => {
  const { t } = useI18n();
  const hasAdvancedFilters = Object.values(filters).some(Boolean);
  const updateFilter = (key: keyof PressureTestFilters, value: string) => {
    onFiltersChange({ ...filters, [key]: value });
  };

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

      <div className="advanced-filter-grid" aria-label={t('advanced_filters')}>
        <label><span>{t('filter_log_no')}</span><input value={filters.logNo} onChange={(event) => updateFilter('logNo', event.target.value)} placeholder={t('filter_log_no_placeholder')} /></label>
        <label><span>{t('filter_date')}</span><input type="date" value={filters.testDate} onChange={(event) => updateFilter('testDate', event.target.value)} /></label>
        <label><span>{t('filter_operator')}</span><input value={filters.operator} onChange={(event) => updateFilter('operator', event.target.value)} placeholder={t('filter_operator_placeholder')} /></label>
        <label><span>{t('filter_bundle')}</span><input value={filters.bundle} onChange={(event) => updateFilter('bundle', event.target.value)} placeholder={t('filter_bundle_placeholder')} /></label>
        <label><span>{t('filter_pipe')}</span><input value={filters.pipe} onChange={(event) => updateFilter('pipe', event.target.value)} placeholder={t('filter_pipe_placeholder')} /></label>
        <button type="button" className="filter-clear-button" disabled={!hasAdvancedFilters} onClick={() => onFiltersChange({ ...EMPTY_PRESSURE_TEST_FILTERS })}>{t('filter_clear')}</button>
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
            {t('filter_recent')}
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
          <div style={{ display: 'flex', background: 'var(--bg-inset-60)', padding: '3px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
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
