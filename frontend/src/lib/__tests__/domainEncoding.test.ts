import { toTranslateGoogHostname } from '../translateProxy';

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed:\nExpected: "${expected}"\nGot:      "${actual}"`);
  }
}

assertEqual(toTranslateGoogHostname('whizzper.app'), 'whizzper-app.translate.goog');
assertEqual(
  toTranslateGoogHostname('web-production-d2649.up.railway.app'),
  'web--production--d2649-up-railway-app.translate.goog',
);
console.log('✓ domainEncoding tests passed!');
