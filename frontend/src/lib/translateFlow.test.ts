import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_TRANSLATE_SOURCE_LANG, openTranslateForShareUrl } from './translateFlow';

describe('openTranslateForShareUrl', () => {
  beforeEach(() => {
    vi.stubGlobal('window', { open: vi.fn() });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens translate.google.com directly with auto source and no fixed target', () => {
    const url = 'https://example.com/transcripts/share/st_abc';
    openTranslateForShareUrl(url);

    expect(DEFAULT_TRANSLATE_SOURCE_LANG).toBe('auto');
    expect(window.open).toHaveBeenCalledWith(
      `https://translate.google.com/?sl=auto&u=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer',
    );
  });
});
