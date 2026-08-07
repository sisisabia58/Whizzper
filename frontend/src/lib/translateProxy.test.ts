import { describe, expect, it } from 'vitest';
import { generateGoogleTranslateProxyUrl } from './translateProxy';

describe('generateGoogleTranslateProxyUrl', () => {
  it('builds translate.goog URLs for public domains', () => {
    const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
    expect(generateGoogleTranslateProxyUrl(publicUrl, 'en', 'id')).toBe(
      'https://whizzper-app.translate.goog/transcripts/share/st_12345?_x_tr_sl=en&_x_tr_tl=id&_x_tr_hl=en-US&_x_tr_pto=wapp',
    );
  });

  it('falls back to translate.google.com for localhost', () => {
    const localUrl = 'http://localhost:8000/transcripts/share/st_12345';
    expect(generateGoogleTranslateProxyUrl(localUrl, 'auto', 'es')).toBe(
      'https://translate.google.com/translate?sl=auto&tl=es&u=' + encodeURIComponent(localUrl),
    );
  });
});
