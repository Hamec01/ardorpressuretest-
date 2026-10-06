const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
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
  return window.fetch(input, {
    ...init,
    headers,
    credentials: 'same-origin',
  });
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
