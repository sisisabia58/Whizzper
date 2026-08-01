/**
 * Generates a Google Translate proxy URL for a given public page URL.
 * Uses the `.translate.goog` hostname (same as TurboScribe). Omits `_x_tr_pto=wapp`
 * which can trigger lazy viewport-only translation in Google's web-app mode.
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
      const encodedUrl = encodeURIComponent(pageUrl);
      return `https://translate.google.com/translate?sl=${encodeURIComponent(
        sourceLang
      )}&tl=${encodeURIComponent(targetLang)}&u=${encodedUrl}`;
    }

    const convertedHost = `${hostname.replace(/-/g, '--').replace(/\./g, '-')}.translate.goog`;
    const searchParams = new URLSearchParams(parsed.search);
    searchParams.set('_x_tr_sl', sourceLang);
    searchParams.set('_x_tr_tl', targetLang);
    searchParams.set('_x_tr_hl', 'en-US');

    const searchString = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return `https://${convertedHost}${parsed.pathname}${searchString}`;
  } catch {
    return `https://translate.google.com/translate?sl=${encodeURIComponent(
      sourceLang
    )}&tl=${encodeURIComponent(targetLang)}&u=${encodeURIComponent(pageUrl)}`;
  }
}

/**
 * Opens the Google Translate proxy URL in a new browser tab with noopener,noreferrer flags.
 */
export function openGoogleTranslateProxy(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang: string = 'en'
): void {
  const proxyUrl = generateGoogleTranslateProxyUrl(pageUrl, sourceLang, targetLang);
  window.open(proxyUrl, '_blank', 'noopener,noreferrer');
}
