/**
 * Generates a Google Translate proxy URL for a given public page URL.
 * Uses the `.translate.goog` hostname (same as TurboScribe).
 */
export function generateGoogleTranslateProxyUrl(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang: string = 'en'
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
      return buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
    }

    const convertedHost = `${hostname.replace(/-/g, '--').replace(/\./g, '-')}.translate.goog`;
    const searchParams = new URLSearchParams(parsed.search);
    searchParams.set('_x_tr_sl', sourceLang);
    searchParams.set('_x_tr_tl', targetLang);
    searchParams.set('_x_tr_hl', 'en-US');
    searchParams.set('_x_tr_pto', 'wapp');

    const searchString = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return `https://${convertedHost}${parsed.pathname}${searchString}`;
  } catch {
    return buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
  }
}

/** Fallback URL served from translate.google.com (localhost and error paths). */
export function buildTranslateGoogleComUrl(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang: string = 'en'
): string {
  const encodedUrl = encodeURIComponent(pageUrl);
  return `https://translate.google.com/translate?sl=${encodeURIComponent(
    sourceLang
  )}&tl=${encodeURIComponent(targetLang)}&u=${encodedUrl}`;
}

/**
 * Opens the Google Translate proxy URL in a new tab.
 * Do not pass noopener/noreferrer — some browsers reset the connection without referrer.
 */
export function openGoogleTranslateProxy(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang: string = 'en'
): void {
  const proxyUrl = generateGoogleTranslateProxyUrl(pageUrl, sourceLang, targetLang);
  const googleComUrl = buildTranslateGoogleComUrl(pageUrl, sourceLang, targetLang);
  const opened = window.open(proxyUrl, '_blank');
  if (!opened) {
    const fallback = window.open(googleComUrl, '_blank');
    if (!fallback) {
      window.location.href = googleComUrl;
    }
  }
}
