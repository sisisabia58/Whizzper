/**
 * Generates a Google Translate proxy URL for a given public page URL.
 * Uses translate.google.com/translate (TurboScribe style) so GT pre-translates
 * the full page server-side instead of lazy viewport translation on .translate.goog.
 */
export function generateGoogleTranslateProxyUrl(
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
