import { openGoogleTranslateProxy } from './translateProxy';

export const DEFAULT_TRANSLATE_SOURCE_LANG = 'auto';
export const DEFAULT_TRANSLATE_TARGET_LANG = 'en';

export function openTranslateForShareUrl(sharePageUrl: string): void {
  openGoogleTranslateProxy(
    sharePageUrl,
    DEFAULT_TRANSLATE_SOURCE_LANG,
    DEFAULT_TRANSLATE_TARGET_LANG,
  );
}
