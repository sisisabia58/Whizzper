/**
 * Google Translate web proxy URLs for public share pages.
 *
 * Uses `https://translate.google.com/?sl=...&u=...` (not `.translate.goog`).
 * The `.translate.goog` subdomain (TurboScribe-style) 302s from `/translate?` and
 * can ERR_CONNECTION_RESET on some networks/clients; the `/?` form stays on
 * translate.google.com and matches improvement-v4 UX (direct open, pick language in GT).
 */

/** Encode hostname for `.translate.goog` (kept for tests / reference). */
export function toTranslateGoogHostname(hostname: string): string {
  return `${hostname.replace(/-/g, '--').replace(/\./g, '-')}.translate.goog`;
}

export function buildTranslateGoogleComUrl(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang?: string
): string {
  const params = new URLSearchParams();
  params.set('sl', sourceLang);
  if (targetLang) {
    params.set('tl', targetLang);
  }
  params.set('u', pageUrl);
  return `https://translate.google.com/?${params.toString()}`;
}

export function generateGoogleTranslateProxyUrl(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang?: string
): string {
  try {
    const parsed = new URL(pageUrl);
    const hostname = parsed.hostname.toLowerCase();

    const isLocalhost =
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '0.0.0.0' ||
      /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname);

    if (isLocalhost || !hostname.includes('.')) {
      // Google cannot proxy localhost; caller should block before opening.
      return buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
    }

    return buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
  } catch {
    return buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
  }
}

/** Opens Google Translate in a new tab (improvement-v4 behavior). */
export function openGoogleTranslateProxy(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang?: string
): void {
  const proxyUrl = generateGoogleTranslateProxyUrl(pageUrl, sourceLang, targetLang);
  window.open(proxyUrl, '_blank', 'noopener,noreferrer');
}
