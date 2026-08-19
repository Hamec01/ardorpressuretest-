import React from 'react';
import { ShieldCheck, Database } from 'lucide-react';

interface HeaderProps {
  totalCount: number;
}

export const Header: React.FC<HeaderProps> = ({ totalCount }) => {
  return (
    <header className="app-header">
      <div className="header-inner">
        <a href="/" className="brand-badge">
          <div className="brand-logo-icon">A</div>
          <div>
            <div className="brand-title">ARDOR Pressure Test</div>
            <div className="brand-subtitle">Pipeline & Vessel Traceability Hub</div>
          </div>
        </a>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            <Database size={16} color="var(--accent-cyan)" />
            <span>Indexed: <strong style={{ color: 'var(--text-primary)' }}>{totalCount}</strong> tests</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.1)', padding: '0.3rem 0.75rem', borderRadius: '9999px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
            <ShieldCheck size={15} />
            <span>Local Node Online</span>
          </div>
        </div>
      </div>
    </header>
  );
};
