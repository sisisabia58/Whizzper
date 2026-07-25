import {
  DOMSegment,
  formatSRTTimestamp,
  formatVTTTimestamp,
  exportToSRT,
  exportToVTT,
  exportToTXT
} from '../transcriptExport';

function assertEqual(actual: string, expected: string) {
  if (actual !== expected) {
    throw new Error(`Assertion failed: expected "${expected}", got "${actual}"`);
  }
}

function assertContains(haystack: string, needle: string) {
  if (!haystack.includes(needle)) {
    throw new Error(`Assertion failed: expected output to include "${needle}"`);
  }
}

function testFormattersAndExporters() {
  const sampleSegments: DOMSegment[] = [
    { index: 0, start: 1.0, end: 4.5, text: 'First translated line' },
    { index: 1, start: 5.25, end: 8.705, text: 'Second translated line' }
  ];

  // SRT Timestamp format
  assertEqual(formatSRTTimestamp(1.0), '00:00:01,000');
  assertEqual(formatSRTTimestamp(3665.123), '01:01:05,123');

  // VTT Timestamp format
  assertEqual(formatVTTTimestamp(1.0), '00:00:01.000');
  assertEqual(formatVTTTimestamp(3665.123), '01:01:05.123');

  // SRT Export
  const srt = exportToSRT(sampleSegments);
  assertContains(srt, '1\n00:00:01,000 --> 00:00:04,500\nFirst translated line');
  assertContains(srt, '2\n00:00:05,250 --> 00:00:08,705\nSecond translated line');

  // VTT Export
  const vtt = exportToVTT(sampleSegments);
  if (!vtt.startsWith('WEBVTT')) {
    throw new Error('Assertion failed: VTT must start with WEBVTT');
  }
  assertContains(vtt, '1\n00:00:01.000 --> 00:00:04.500\nFirst translated line');

  // TXT Export
  const txt = exportToTXT(sampleSegments);
  assertEqual(txt, 'First translated line\nSecond translated line');

  console.log('✓ transcriptExport formatters and exporters passed');
}

testFormattersAndExporters();
