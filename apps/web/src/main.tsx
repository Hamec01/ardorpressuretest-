import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { PublicLogView } from './components/PublicLogView';
import { SetPasswordPage } from './components/SetPasswordPage';
import { AuthProvider } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { ThemeProvider, applyStoredThemeSync } from './context/ThemeContext';
import './index.css';

// Apply the persisted theme before first paint to avoid a dark->light flash.
applyStoredThemeSync();

const shareMatch = window.location.pathname.match(/^\/share\/([^/]+)\/?$/);
const setPasswordMatch = window.location.pathname.match(/^\/set-password\/([A-Za-z0-9_-]+)\/?$/);
const root = ReactDOM.createRoot(document.getElementById('root')!);

if (setPasswordMatch) {
  root.render(
    <React.StrictMode>
      <ThemeProvider>
        <LanguageProvider>
          <SetPasswordPage token={setPasswordMatch[1]} />
        </LanguageProvider>
      </ThemeProvider>
    </React.StrictMode>,
  );
} else if (shareMatch) {
  const logNo = decodeURIComponent(shareMatch[1]);
  root.render(
    <React.StrictMode>
      <ThemeProvider>
        <LanguageProvider>
          <PublicLogView logNo={logNo} />
        </LanguageProvider>
      </ThemeProvider>
    </React.StrictMode>,
  );
} else {
  root.render(
    <React.StrictMode>
      <ThemeProvider>
        <AuthProvider>
          <LanguageProvider>
            <App />
          </LanguageProvider>
        </AuthProvider>
      </ThemeProvider>
    </React.StrictMode>,
  );
}
