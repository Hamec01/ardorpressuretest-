import React from 'react';
import { Search, X } from 'lucide-react';

interface SearchFiltersProps {
  query: string;
  onQueryChange: (q: string) => void;
  activeFilter: string;
  onFilterSelect: (filter: string) => void;
}

export const SearchFilters: React.FC<SearchFiltersProps> = ({
  query,
  onQueryChange,
  activeFilter,
  onFilterSelect
}) => {
  return (
    <div className="search-section">
      <div className="search-input-wrapper">
        <Search className="search-icon" size={22} />
        <input
          type="text"
          className="search-input"
          placeholder="Search by Log No. (e.g. 014FED), Pipe No. (e.g. P-101), Bundle, Operator or Project..."
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
    </div>
  );
};
