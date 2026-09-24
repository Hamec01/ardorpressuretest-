const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

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
