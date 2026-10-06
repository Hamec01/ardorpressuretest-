import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useI18n } from '../context/LanguageContext';
import { LoginPage } from './LoginPage';

/** Only signed-in employees reach the application; everyone else sees the sign-in page. */
export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoading } = useAuth();
  const { t } = useI18n();
  if (isLoading) {
    return (
      <div className="auth-page">
        <div className="auth-card"><p className="auth-muted">{t('login_loading')}</p></div>
      </div>
    );
  }
  if (!user) return <LoginPage />;
  return <>{children}</>;
};
