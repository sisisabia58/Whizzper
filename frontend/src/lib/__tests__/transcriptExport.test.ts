import assert from 'node:assert';
import {
  DOMSegment,
  formatSRTTimestamp,
  formatVTTTimestamp,
  exportToSRT,
  exportToVTT,
  exportToTXT
} from '../transcriptExport';

function testFormattersAndExporters() {
  const sampleSegments: DOMSegment[] = [
    { index: 0, start: 1.0, end: 4.5, text: 'First translated line' },
    { index: 1, start: 5.25, end: 8.705, text: 'Second translated line' }
  ];

  // SRT Timestamp format
  assert.strictEqual(formatSRTTimestamp(1.0), '00:00:01,000');
  assert.strictEqual(formatSRTTimestamp(3665.123), '01:01:05,123');

  // VTT Timestamp format
  assert.strictEqual(formatVTTTimestamp(1.0), '00:00:01.000');
  assert.strictEqual(formatVTTTimestamp(3665.123), '01:01:05.123');

  // SRT Export
  const srt = exportToSRT(sampleSegments);
  assert.ok(srt.includes('1\n00:00:01,000 --> 00:00:04,500\nFirst translated line'));
  assert.ok(srt.includes('2\n00:00:05,250 --> 00:00:08,705\nSecond translated line'));

  // VTT Export
  const vtt = exportToVTT(sampleSegments);
  assert.ok(vtt.startsWith('WEBVTT'));
  assert.ok(vtt.includes('1\n00:00:01.000 --> 00:00:04.500\nFirst translated line'));

  // TXT Export
  const txt = exportToTXT(sampleSegments);
  assert.strictEqual(txt, 'First translated line\nSecond translated line');

  console.log('✓ transcriptExport formatters and exporters passed');
}

testFormattersAndExporters();
