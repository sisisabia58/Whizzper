import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DEFAULT_TRANSLATE_SOURCE_LANG,
  DEFAULT_TRANSLATE_TARGET_LANG,
  openTranslateForShareUrl,
} from './translateFlow';

describe('openTranslateForShareUrl', () => {
  beforeEach(() => {
    vi.stubGlobal('window', {
      open: vi.fn(() => null),
      location: { href: '' },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens Google Translate directly with auto/en defaults', () => {
    const url = 'https://example.com/transcripts/share/st_abc';
    openTranslateForShareUrl(url);

    expect(DEFAULT_TRANSLATE_SOURCE_LANG).toBe('auto');
    expect(DEFAULT_TRANSLATE_TARGET_LANG).toBe('en');
    expect(window.open).toHaveBeenCalled();
    expect(
      (window.open as ReturnType<typeof vi.fn>).mock.calls.some((call) =>
        String(call[0]).includes('translate'),
      ),
    ).toBe(true);
  });
});
