/**
 * Token persistence. Kept tiny and separate so the client and auth layers can
 * both touch it without a circular import.
 *
 * Stored in localStorage so a page refresh keeps the session. (The backend token
 * has no expiry yet — a known gap; when expiry lands we revalidate via /auth/me.)
 */
const KEY = "ng.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    /* storage unavailable (private mode) — session just won't persist */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* no-op */
  }
}
