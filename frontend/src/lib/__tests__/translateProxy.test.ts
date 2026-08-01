import { generateGoogleTranslateProxyUrl } from '../translateProxy';

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: "${expected}"\nGot:      "${actual}"`);
  }
}

function testGenerateProxyUrl() {
  const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
  const proxyUrl = generateGoogleTranslateProxyUrl(publicUrl, 'en', 'id');
  assertEqual(
    proxyUrl,
    'https://translate.google.com/translate?sl=en&tl=id&u=' + encodeURIComponent(publicUrl)
  );

  const railwayUrl = 'https://web-production-d2649.up.railway.app/transcripts/share/st_12345';
  const railwayProxyUrl = generateGoogleTranslateProxyUrl(railwayUrl, 'auto', 'en');
  assertEqual(
    railwayProxyUrl,
    'https://translate.google.com/translate?sl=auto&tl=en&u=' + encodeURIComponent(railwayUrl)
  );

  const localUrl = 'http://localhost:8000/transcripts/share/st_12345';
  const localProxyUrl = generateGoogleTranslateProxyUrl(localUrl, 'auto', 'es');
  assertEqual(
    localProxyUrl,
    'https://translate.google.com/translate?sl=auto&tl=es&u=' + encodeURIComponent(localUrl)
  );

  console.log('✓ translateProxy tests passed!');
}

testGenerateProxyUrl();
