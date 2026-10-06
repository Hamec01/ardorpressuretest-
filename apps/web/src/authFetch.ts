const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
export const SESSION_EXPIRED_EVENT = 'ardor-session-expired';
let transitionalBearerToken: string | null = null;

// HTTP staging cannot receive the production-only Secure browser cookie. Keep the
// already-issued transitional token in memory only: never localStorage/sessionStorage.
export function setTransitionalBearerToken(token: string | null): void {
  transitionalBearerToken = token;
}

function readCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split(';')) {
    const value = part.trim();
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length));
    }
  }
  return null;
}

export function readCsrfToken(): string | null {
  return readCookie('__Host-ardor_csrf') ?? readCookie('ardor_csrf');
}

export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (transitionalBearerToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${transitionalBearerToken}`);
  }
  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCsrfToken();
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  }
  const response = await window.fetch(input, {
    ...init,
    headers,
    credentials: 'same-origin',
  });
  // A business request answered 401 means the session ended (expired, revoked, signed out
  // elsewhere): the AuthGate shows the sign-in page again. Login and change-password use
  // 401 for a wrong password, which is not an ended session.
  const url = String(input);
  if (response.status === 401 && !url.includes('/api/v1/auth/login') && !url.includes('/api/v1/auth/change-password')) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return response;
}

/**
 * Anonymous request for the few public endpoints (one-time password links): never sends
 * cookies, auth or CSRF headers, so a signed-in browser cannot leak its session.
 */
export async function publicFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  return window.fetch(input, { ...init, credentials: 'omit' });
}
