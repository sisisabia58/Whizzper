export function fileSelectionToggleClasses(checked: boolean): string {
  return `w-5 h-5 shrink-0 rounded-md border flex items-center justify-center transition-colors ${
    checked ? 'bg-ink border-ink text-paper' : 'bg-paper border-zinc-300'
  }`;
}
