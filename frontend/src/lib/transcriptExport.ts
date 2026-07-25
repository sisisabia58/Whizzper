export interface DOMSegment {
  index: number;
  start: number;
  end: number;
  text: string;
}

export interface ExtractionResult {
  segments: DOMSegment[];
  error?: string;
}

function pad(num: number, len: number = 2): string {
  return String(num).padStart(len, '0');
}

export function formatSRTTimestamp(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(ms, 3)}`;
}

export function formatVTTTimestamp(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)}.${pad(ms, 3)}`;
}

/**
 * Scrapes translated spoken text and preserved timing metadata from the DOM.
 */
export function extractDOMTranscript(
  containerSelector: string = '#transcript-container'
): ExtractionResult {
  if (typeof document === 'undefined') {
    return { segments: [], error: 'DOM environment not available' };
  }

  const container = document.querySelector(containerSelector);
  if (!container) {
    return { segments: [], error: 'Transcript container element not found' };
  }

  const expectedTotalAttr = container.getAttribute('data-total');
  const expectedTotal = expectedTotalAttr ? parseInt(expectedTotalAttr, 10) : 0;

  const lineElements = Array.from(container.querySelectorAll('.transcript-line'));
  const segments: DOMSegment[] = [];

  for (const el of lineElements) {
    const idxAttr = el.getAttribute('data-index');
    const startAttr = el.getAttribute('data-start');
    const endAttr = el.getAttribute('data-end');
    const text = (el as HTMLElement).innerText ? (el as HTMLElement).innerText.trim() : '';

    if (idxAttr === null || startAttr === null || endAttr === null || !text) {
      continue;
    }

    const index = parseInt(idxAttr, 10);
    const start = parseFloat(startAttr);
    const end = parseFloat(endAttr);

    if (isNaN(index) || isNaN(start) || isNaN(end)) {
      continue;
    }

    segments.push({ index, start, end, text });
  }

  segments.sort((a, b) => a.index - b.index);

  if (expectedTotal > 0 && segments.length !== expectedTotal) {
    return {
      segments,
      error: `Line count mismatch: expected ${expectedTotal} segments but extracted ${segments.length}`
    };
  }

  return { segments };
}

export function exportToSRT(segments: DOMSegment[]): string {
  return segments
    .map(
      (s, i) =>
        `${i + 1}\n${formatSRTTimestamp(s.start)} --> ${formatSRTTimestamp(s.end)}\n${s.text}\n`
    )
    .join('\n');
}

export function exportToVTT(segments: DOMSegment[]): string {
  const lines = segments
    .map(
      (s, i) =>
        `${i + 1}\n${formatVTTTimestamp(s.start)} --> ${formatVTTTimestamp(s.end)}\n${s.text}\n`
    )
    .join('\n');
  return `WEBVTT\n\n${lines}`;
}

export function exportToTXT(segments: DOMSegment[]): string {
  return segments.map((s) => s.text).join('\n');
}

export function downloadFile(content: string, filename: string, mimeType: string): void {
  if (typeof document === 'undefined') return;
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
