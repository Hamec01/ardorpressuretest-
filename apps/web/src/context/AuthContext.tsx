import React, { createContext, useContext, useState, useEffect } from 'react';
import { authFetch, SESSION_EXPIRED_EVENT, setTransitionalBearerToken } from '../authFetch';

/** Sign-in failure with the HTTP status (401 wrong credentials, 429 too many attempts). */
export class LoginError extends Error {
  status: number;
  retryAfterSeconds: number | null;
  constructor(status: number, message: string, retryAfterSeconds: number | null) {
    super(message);
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export interface AuthUser {
  id: string;
  username: string;
  full_name: string | null;
  role: 'viewer' | 'operator' | 'foreman' | 'admin';
  email?: string | null;
  must_change_password: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  login: (username: string, password: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await authFetch('/api/v1/auth/me');
        if (res.ok) {
          const userData = await res.json();
          setUser(userData);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();

    const onExpired = () => {
      setTransitionalBearerToken(null);
      setUser(null);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const login = async (username: string, password: string) => {
    const res = await authFetch('/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Ardor-Session-Mode': 'browser',
      },
      body: JSON.stringify({ username, password })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const retryAfter = Number(res.headers.get('Retry-After'));
      throw new LoginError(res.status, err.detail || 'Login failed', Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null);
    }

    const data = await res.json();
    setTransitionalBearerToken(typeof data.access_token === 'string' ? data.access_token : null);
    setUser(data.user);
  };

  const logout = async () => {
    try {
      const res = await authFetch('/api/v1/auth/logout', { method: 'POST' });
      if (res.ok || res.status === 401) {
        setTransitionalBearerToken(null);
        setUser(null);
      }
    } catch {
      // Keep the authenticated UI state when the server did not confirm logout.
    }
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    const res = await authFetch('/api/v1/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Password change failed');
    }
    setUser((current) => current ? { ...current, must_change_password: false } : current);
  };

  return (
    <AuthContext.Provider value={{ user, login, changePassword, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
