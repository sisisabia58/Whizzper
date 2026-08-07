import { buildTranslateGoogleComUrl, toTranslateGoogHostname } from '../translateProxy';

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: "${expected}"\nGot:      "${actual}"`);
  }
}

function testTranslateUrls() {
  const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
  assertEqual(
    buildTranslateGoogleComUrl(publicUrl, 'auto'),
    `https://translate.google.com/?sl=auto&u=${encodeURIComponent(publicUrl)}`,
  );

  const railwayUrl = 'https://web-production-d2649.up.railway.app/transcripts/share/st_12345';
  assertEqual(
    buildTranslateGoogleComUrl(railwayUrl, 'auto'),
    `https://translate.google.com/?sl=auto&u=${encodeURIComponent(railwayUrl)}`,
  );

  assertEqual(
    toTranslateGoogHostname('web-production-d2649.up.railway.app'),
    'web--production--d2649-up-railway-app.translate.goog',
  );

  const localUrl = 'http://localhost:8000/transcripts/share/st_12345';
  assertEqual(
    buildTranslateGoogleComUrl(localUrl, 'auto', 'es'),
    `https://translate.google.com/?sl=auto&tl=es&u=${encodeURIComponent(localUrl)}`,
  );

  console.log('✓ translateProxy tests passed!');
}

testTranslateUrls();
