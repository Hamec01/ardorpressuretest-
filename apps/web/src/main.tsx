import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { PublicLogView } from './components/PublicLogView';
import { AuthProvider } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { ThemeProvider, applyStoredThemeSync } from './context/ThemeContext';
import './index.css';

// Apply the persisted theme before first paint to avoid a dark->light flash.
applyStoredThemeSync();

const shareMatch = window.location.pathname.match(/^\/share\/([^/]+)\/?$/);
const root = ReactDOM.createRoot(document.getElementById('root')!);

if (shareMatch) {
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
