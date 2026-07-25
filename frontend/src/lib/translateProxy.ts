/**
 * Generates a Google Translate proxy URL for a given public page URL.
 * Converts public domain dots to hyphens and appends `.translate.goog`.
 * Falls back to `translate.google.com` for localhost, IP addresses, or non-standard ports.
 */
export function generateGoogleTranslateProxyUrl(
  pageUrl: string,
  sourceLang: string = 'auto',
  targetLang: string = 'en'
): string {
  try {
    const parsed = new URL(pageUrl);
    const hostname = parsed.hostname.toLowerCase();

    // Check for localhost or IP address fallback
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

    // Convert domain dots to hyphens: e.g. whizzper.app -> whizzper-app.translate.goog
    const convertedHost = `${hostname.replace(/\./g, '-')}.translate.goog`;
    const protocol = 'https:';

    const searchParams = new URLSearchParams(parsed.search);
    searchParams.set('_x_tr_sl', sourceLang);
    searchParams.set('_x_tr_tl', targetLang);
    searchParams.set('_x_tr_hl', 'en-US');
    searchParams.set('_x_tr_pto', 'wapp');

    const searchString = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return `${protocol}//${convertedHost}${parsed.pathname}${searchString}`;
  } catch {
    // If URL parsing fails, fallback to Google Translate main portal
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
