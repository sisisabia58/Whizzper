import { openGoogleTranslateProxy } from './translateProxy';

export const DEFAULT_TRANSLATE_SOURCE_LANG = 'auto';

/** Direct redirect to Google Translate; user picks target language in the GT UI. */
export function openTranslateForShareUrl(sharePageUrl: string): void {
  openGoogleTranslateProxy(sharePageUrl, DEFAULT_TRANSLATE_SOURCE_LANG);
}
