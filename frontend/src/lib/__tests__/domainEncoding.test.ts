function convertHostToTranslateGoog(hostname: string): string {
  const converted = hostname.replace(/-/g, '--').replace(/\./g, '-');
  return `${converted}.translate.goog`;
}

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed: expected "${expected}", got "${actual}"`);
  }
}

console.log('Testing domain encoding:');
assertEqual(convertHostToTranslateGoog('whizzper.app'), 'whizzper-app.translate.goog');
assertEqual(convertHostToTranslateGoog('web-production-d2649.up.railway.app'), 'web--production--d2649-up-railway-app.translate.goog');

console.log('✓ All domain encoding tests passed!');
