/**
 * Path-scoped cookie storage for Zustand persist.
 * Cookies with Path=/redtrip/ are not visible to JS on /vesta /cardio /bizatlas.
 */
const COOKIE_PATH = "/redtrip/";

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) {
      try {
        return decodeURIComponent(part.slice(prefix.length));
      } catch {
        return part.slice(prefix.length);
      }
    }
  }
  return null;
}

function writeCookie(name: string, value: string, maxAgeSec: number): void {
  if (typeof document === "undefined") return;
  const secure =
    typeof location !== "undefined" && location.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie =
    `${encodeURIComponent(name)}=${encodeURIComponent(value)}` +
    `; Path=${COOKIE_PATH}; Max-Age=${maxAgeSec}; SameSite=Lax${secure}`;
}

function clearCookie(name: string): void {
  if (typeof document === "undefined") return;
  document.cookie =
    `${encodeURIComponent(name)}=; Path=${COOKIE_PATH}; Max-Age=0; SameSite=Lax`;
}

/** Zustand StateStorage backed by path-scoped cookies (≈4KB limit). */
export const redtripCookieStorage = {
  getItem(name: string): string | null {
    return readCookie(name);
  },
  setItem(name: string, value: string): void {
    // 30 days — align with refresh token TTL
    writeCookie(name, value, 60 * 60 * 24 * 30);
  },
  removeItem(name: string): void {
    clearCookie(name);
  },
};
