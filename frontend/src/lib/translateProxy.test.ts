import { describe, expect, it } from 'vitest';
import {
  buildTranslateGoogleComUrl,
  generateGoogleTranslateProxyUrl,
  toTranslateGoogHostname,
} from './translateProxy';

describe('toTranslateGoogHostname', () => {
  it('encodes hostnames for translate.goog reference', () => {
    expect(toTranslateGoogHostname('whizzper.app')).toBe('whizzper-app.translate.goog');
    expect(toTranslateGoogHostname('web-production-d2649.up.railway.app')).toBe(
      'web--production--d2649-up-railway-app.translate.goog',
    );
  });
});

describe('buildTranslateGoogleComUrl', () => {
  it('uses translate.google.com root with sl and u params', () => {
    const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
    expect(buildTranslateGoogleComUrl(publicUrl, 'auto')).toBe(
      `https://translate.google.com/?sl=auto&u=${encodeURIComponent(publicUrl)}`,
    );
  });

  it('includes tl when provided', () => {
    const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
    expect(buildTranslateGoogleComUrl(publicUrl, 'en', 'id')).toBe(
      `https://translate.google.com/?sl=en&tl=id&u=${encodeURIComponent(publicUrl)}`,
    );
  });
});

describe('generateGoogleTranslateProxyUrl', () => {
  it('uses translate.google.com for public domains', () => {
    const railwayUrl = 'https://web-production-d2649.up.railway.app/transcripts/share/st_12345';
    expect(generateGoogleTranslateProxyUrl(railwayUrl, 'auto')).toBe(
      `https://translate.google.com/?sl=auto&u=${encodeURIComponent(railwayUrl)}`,
    );
  });

  it('builds localhost URL for dev (caller blocks if unreachable)', () => {
    const localUrl = 'http://localhost:8000/transcripts/share/st_12345';
    expect(generateGoogleTranslateProxyUrl(localUrl, 'auto', 'es')).toBe(
      `https://translate.google.com/?sl=auto&tl=es&u=${encodeURIComponent(localUrl)}`,
    );
  });
});
