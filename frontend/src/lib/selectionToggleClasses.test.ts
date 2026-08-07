import { describe, expect, it } from 'vitest';
import { fileSelectionToggleClasses } from './selectionToggleClasses';

describe('fileSelectionToggleClasses', () => {
  it('uses valid Tailwind size utilities', () => {
    const classes = fileSelectionToggleClasses(true);
    expect(classes).toContain('w-5');
    expect(classes).toContain('h-5');
    expect(classes).not.toContain('w-4.5');
    expect(classes).not.toContain('h-4.5');
  });

  it('applies checked styles when selected', () => {
    expect(fileSelectionToggleClasses(true)).toContain('bg-ink');
    expect(fileSelectionToggleClasses(false)).toContain('border-zinc-300');
  });
});
