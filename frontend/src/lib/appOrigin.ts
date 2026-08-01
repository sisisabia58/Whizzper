/**
 * Resolves the origin used for public share/translate URLs.
 * Google Translate's `.translate.goog` proxy requires a publicly reachable hostname;
 * `localhost` always fails because Google's servers cannot fetch your machine.
 */
let cachedPublicAppUrl: string | null = null;

function hostnameFromOrigin(origin: string): string {
  try {
    return new URL(origin).hostname.toLowerCase();
  } catch {
    return '';
  }
}

export function isLocalHostname(hostname: string): boolean {
  const h = hostname.toLowerCase();
  return (
    h === 'localhost' ||
    h === '127.0.0.1' ||
    h === '0.0.0.0' ||
    /^(\d{1,3}\.){3}\d{1,3}$/.test(h)
  );
}

export function isLocalOrigin(origin?: string): boolean {
  const host = origin ? hostnameFromOrigin(origin) : window.location.hostname.toLowerCase();
  return isLocalHostname(host);
}

export async function fetchPublicAppUrl(): Promise<string | null> {
  if (cachedPublicAppUrl) return cachedPublicAppUrl;
  try {
    const resp = await fetch('/api/config/client');
    if (!resp.ok) return null;
    const data = await resp.json();
    const url = (data.public_app_url as string | undefined)?.trim().replace(/\/$/, '');
    if (url) {
      cachedPublicAppUrl = url;
      return url;
    }
  } catch {
    // ignore — fall back to window.location.origin
  }
  return null;
}

/** Origin for share pages opened via Google Translate (public URL when configured). */
export async function resolveSharePageOrigin(): Promise<string> {
  if (!isLocalOrigin()) {
    return window.location.origin;
  }
  const publicUrl = await fetchPublicAppUrl();
  if (publicUrl) {
    return publicUrl;
  }
  return window.location.origin;
}

export function buildSharePageUrl(origin: string, sharePath: string): string {
  const path = sharePath.startsWith('/') ? sharePath : `/${sharePath}`;
  return `${origin.replace(/\/$/, '')}${path}`;
}

export function googleTranslateProxySupported(pageUrl: string): boolean {
  try {
    const host = new URL(pageUrl).hostname.toLowerCase();
    return !isLocalHostname(host) && host.includes('.');
  } catch {
    return false;
  }
}
