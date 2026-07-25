import { generateGoogleTranslateProxyUrl } from '../translateProxy';

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed: expected "${expected}", got "${actual}"`);
  }
}

function testGenerateProxyUrl() {
  const publicUrl = 'https://whizzper.app/transcripts/share/st_12345';
  const proxyUrl = generateGoogleTranslateProxyUrl(publicUrl, 'en', 'id');
  assertEqual(
    proxyUrl,
    'https://whizzper-app.translate.goog/transcripts/share/st_12345?_x_tr_sl=en&_x_tr_tl=id&_x_tr_hl=en-US&_x_tr_pto=wapp'
  );

  const localUrl = 'http://localhost:8000/transcripts/share/st_12345';
  const localProxyUrl = generateGoogleTranslateProxyUrl(localUrl, 'auto', 'es');
  assertEqual(
    localProxyUrl,
    'https://translate.google.com/translate?sl=auto&tl=es&u=' + encodeURIComponent(localUrl)
  );

  console.log('✓ translateProxy tests passed');
}

testGenerateProxyUrl();
