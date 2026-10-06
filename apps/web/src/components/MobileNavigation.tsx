import React, { useState } from 'react';
import {
  ClipboardList,
  BarChart3,
  FileSpreadsheet,
  HelpCircle,
  Layers,
  LogIn,
  LogOut,
  Menu,
  Moon,
  Plus,
  ShieldAlert,
  Sun,
  Trash2,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';
import { Language } from '../i18n';

export type AppTab = 'tests' | 'trash' | 'plans' | 'records' | 'statistics' | 'faq';

interface MobileNavigationProps {
  activeTab: AppTab;
  totalCount: number;
  onTabChange: (tab: AppTab) => void;
  onNewTest?: () => void;
  onLogin: () => void;
  onAudit: () => void;
  onOpenFaq: () => void;
}

const LANGUAGES: Array<{ code: Language; label: string }> = [
  { code: 'fi', label: 'FI' },
  { code: 'en', label: 'EN' },
  { code: 'ru', label: 'RU' },
];

export const MobileNavigation: React.FC<MobileNavigationProps> = ({
  activeTab,
  totalCount,
  onTabChange,
  onNewTest,
  onLogin,
  onAudit,
  onOpenFaq,
}) => {
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const [moreOpen, setMoreOpen] = useState(false);

  const selectTab = (tab: AppTab) => {
    onTabChange(tab);
    setMoreOpen(false);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <>
      {onNewTest && <button type="button" className="mobile-upload-fab" onClick={onNewTest} aria-label={t('btn_new_test')}>
        <Plus size={24} />
      </button>}

      <nav className="mobile-bottom-nav" aria-label={t('mobile_main_navigation')}>
        <button type="button" className={activeTab === 'tests' ? 'active' : ''} onClick={() => selectTab('tests')} aria-current={activeTab === 'tests' ? 'page' : undefined}>
          <Layers size={21} /><span>{t('mobile_tests')}</span>
        </button>
        <button type="button" className={activeTab === 'plans' ? 'active' : ''} onClick={() => selectTab('plans')} aria-current={activeTab === 'plans' ? 'page' : undefined}>
          <ClipboardList size={21} /><span>{t('mobile_plans')}</span>
        </button>
        <button type="button" className={activeTab === 'records' ? 'active ptr' : 'ptr'} onClick={() => selectTab('records')} aria-current={activeTab === 'records' ? 'page' : undefined}>
          <FileSpreadsheet size={21} /><span>{t('mobile_ptr')}</span>
        </button>
        <button type="button" className={activeTab === 'statistics' ? 'active' : ''} onClick={() => selectTab('statistics')} aria-current={activeTab === 'statistics' ? 'page' : undefined}>
          <BarChart3 size={21} /><span>{t('mobile_statistics')}</span>
        </button>
        <button type="button" className={moreOpen || activeTab === 'trash' ? 'active' : ''} onClick={() => setMoreOpen(true)} aria-expanded={moreOpen}>
          <Menu size={21} /><span>{t('mobile_more')}</span>
        </button>
      </nav>

      {moreOpen && (
        <div className="mobile-sheet-overlay" role="presentation" onClick={() => setMoreOpen(false)}>
          <section className="mobile-more-sheet" role="dialog" aria-modal="true" aria-labelledby="mobile-more-title" onClick={(event) => event.stopPropagation()}>
            <header>
              <div><h2 id="mobile-more-title">{t('mobile_more')}</h2><p>{user?.full_name || t('mobile_guest')}</p></div>
              <button type="button" className="mobile-icon-button" onClick={() => setMoreOpen(false)} aria-label={t('modal_close')}><X size={22} /></button>
            </header>

            {onNewTest && <button type="button" className="mobile-sheet-primary" onClick={() => { setMoreOpen(false); onNewTest(); }}><Plus size={19} />{t('btn_new_test')}</button>}

            <div className="mobile-settings-group">
              <span>{t('mobile_language')}</span>
              <div className="mobile-segmented-control">
                {LANGUAGES.map(({ code, label }) => <button key={code} type="button" className={lang === code ? 'active' : ''} onClick={() => setLang(code)}>{label}</button>)}
              </div>
            </div>

            <button type="button" className="mobile-sheet-row" onClick={toggleTheme}>
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
              <span>{theme === 'light' ? t('mobile_dark_theme') : t('mobile_light_theme')}</span>
            </button>
            <button type="button" className="mobile-sheet-row" onClick={() => selectTab('trash')}><Trash2 size={20} /><span>{t('mobile_trash')}</span></button>
            <button type="button" className="mobile-sheet-row" onClick={() => { setMoreOpen(false); onOpenFaq(); }}><HelpCircle size={20} /><span>{t('mobile_faq')}</span></button>
            {(user?.role === 'admin' || user?.role === 'foreman') && <button type="button" className="mobile-sheet-row" onClick={() => { setMoreOpen(false); onAudit(); }}><ShieldAlert size={20} /><span>{t('btn_audit')}</span></button>}

            <div className="mobile-system-status"><span className="mobile-online-dot" />{t('node_online')} · {t('indexed_count', { count: totalCount })}</div>

            {user ? (
              <button type="button" className="mobile-sheet-row mobile-danger-row" onClick={() => { setMoreOpen(false); logout(); }}><LogOut size={20} /><span>{t('btn_logout')}</span></button>
            ) : (
              <button type="button" className="mobile-sheet-row" onClick={() => { setMoreOpen(false); onLogin(); }}><LogIn size={20} /><span>{t('btn_login')}</span></button>
            )}
          </section>
        </div>
      )}
    </>
  );
};
