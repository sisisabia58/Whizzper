import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FolderOpen,
  Folder,
  FileAudio,
  FileVideo,
  File as FileIcon,
  Loader2,
  Check,
  Search,
  ArrowRight } from
'lucide-react';
import { sampleScannedFiles, ScannedFile } from './transcriptions';
type ScanState = 'idle' | 'scanning' | 'done';
interface DriveScanPanelProps {
  /** reports how many processable files are currently selected */
  onSelectionChange: (count: number) => void;
  /** reports the discovered folder name */
  onFolderChange: (name: string | null) => void;
}
const typeIcon = {
  audio: FileAudio,
  video: FileVideo,
  other: FileIcon
} as const;
export function DriveScanPanel({
  onSelectionChange,
  onFolderChange
}: DriveScanPanelProps) {
  const [link, setLink] = useState('');
  const [state, setState] = useState<ScanState>('idle');
  const [revealed, setRevealed] = useState(0);
  const [scannedCount, setScannedCount] = useState(0);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const timers = useRef<number[]>([]);
  const processable = sampleScannedFiles.filter((f) => f.type !== 'other');
  const selectedCount = processable.filter((f) => !excluded.has(f.id)).length;
  useEffect(() => {
    onSelectionChange(state === 'done' ? selectedCount : 0);
  }, [state, selectedCount, onSelectionChange]);
  useEffect(() => () => timers.current.forEach((t) => clearTimeout(t)), []);
  const startScan = () => {
    if (!link.trim()) return;
    setState('scanning');
    setRevealed(0);
    setScannedCount(0);
    onFolderChange('Podcast — Season 4');
    sampleScannedFiles.forEach((_, i) => {
      const t = window.setTimeout(
        () => {
          setScannedCount(i + 1);
        },
        180 * (i + 1)
      );
      timers.current.push(t);
    });
    const done = window.setTimeout(
      () => {
        setState('done');
        sampleScannedFiles.forEach((_, i) => {
          const rt = window.setTimeout(() => setRevealed(i + 1), 40 * i);
          timers.current.push(rt);
        });
      },
      180 * sampleScannedFiles.length + 300
    );
    timers.current.push(done);
  };
  const toggleFile = (id: string) =>
  setExcluded((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const totalMinutes = processable.
  filter((f) => !excluded.has(f.id)).
  reduce((acc, f) => acc + (f.durationMin ?? 0), 0);
  const skippedCount = sampleScannedFiles.length - processable.length;
  return (
    <div className="space-y-5">
      {/* Link input */}
      <div>
        <label
          htmlFor="drive-link"
          className="block text-sm font-semibold text-ink mb-2">
          
          Google Drive folder link
        </label>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <FolderOpen className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
            <input
              id="drive-link"
              type="url"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startScan()}
              placeholder="https://drive.google.com/drive/folders/…"
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-zinc-300 bg-paper text-sm text-ink placeholder:text-zinc-400 focus:outline-none focus:border-ink focus:ring-1 focus:ring-ink transition-colors" />
            
          </div>
          <button
            onClick={startScan}
            disabled={!link.trim() || state === 'scanning'}
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100 shrink-0">
            
            {state === 'scanning' ?
            <Loader2 className="w-4 h-4 animate-spin" /> :

            <Search className="w-4 h-4" />
            }
            Scan folder
          </button>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          We recursively scan the folder and all subfolders, then queue only
          audio &amp; video files. Other file types are skipped automatically.
        </p>
      </div>

      {/* Scanning state */}
      <AnimatePresence mode="wait">
        {state === 'scanning' &&
        <motion.div
          key="scanning"
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          exit={{
            opacity: 0
          }}
          className="rounded-2xl border border-zinc-200 bg-paper-off p-8 flex flex-col items-center text-center">
          
            <div className="relative w-12 h-12 mb-4">
              <Folder className="w-12 h-12 text-zinc-300" strokeWidth={1.5} />
              <Loader2 className="absolute inset-0 m-auto w-5 h-5 text-ink animate-spin" />
            </div>
            <p className="font-display font-bold text-ink">
              Scanning folder recursively…
            </p>
            <p className="text-sm text-zinc-500 mt-1 tabular-nums">
              {scannedCount} items discovered
            </p>
          </motion.div>
        }

        {/* Result tree */}
        {state === 'done' &&
        <motion.div
          key="done"
          initial={{
            opacity: 0,
            y: 8
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="space-y-3">
          
            {/* Summary bar */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-zinc-200 bg-paper-off px-4 py-3 text-sm">
              <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
                <Check className="w-4 h-4" />
                {selectedCount} files to transcribe
              </span>
              <span className="text-zinc-400">·</span>
              <span className="text-zinc-500 tabular-nums">
                {totalMinutes} min total
              </span>
              <span className="text-zinc-400">·</span>
              <span className="text-zinc-500">{skippedCount} skipped</span>
            </div>

            {/* File list */}
            <div
            className="max-h-64 overflow-y-auto rounded-2xl border border-zinc-200 divide-y divide-zinc-100"
            role="list"
            aria-label="Scanned files">
            
              {sampleScannedFiles.slice(0, revealed).map((f: ScannedFile) => {
              const Icon = typeIcon[f.type];
              const isProcessable = f.type !== 'other';
              const included = isProcessable && !excluded.has(f.id);
              return (
                <motion.div
                  key={f.id}
                  initial={{
                    opacity: 0,
                    x: -6
                  }}
                  animate={{
                    opacity: 1,
                    x: 0
                  }}
                  role="listitem"
                  className={`flex items-center gap-3 px-4 py-2.5 ${isProcessable ? 'bg-paper' : 'bg-paper-off/60'}`}>
                  
                    {isProcessable ?
                  <button
                    onClick={() => toggleFile(f.id)}
                    role="checkbox"
                    aria-checked={included}
                    aria-label={`${included ? 'Exclude' : 'Include'} ${f.name}`}
                    className={`w-5 h-5 shrink-0 rounded-md border flex items-center justify-center transition-colors ${included ? 'bg-ink border-ink text-paper' : 'bg-paper border-zinc-300'}`}>
                    
                        {included &&
                    <svg
                      viewBox="0 0 12 12"
                      className="w-3 h-3"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2.5}>
                      
                            <path
                        d="M2.5 6.5L5 9l4.5-5"
                        strokeLinecap="round"
                        strokeLinejoin="round" />
                      
                          </svg>
                    }
                      </button> :

                  <span className="w-5 h-5 shrink-0" aria-hidden="true" />
                  }

                    <Icon
                    className={`w-4 h-4 shrink-0 ${isProcessable ? 'text-ink' : 'text-zinc-300'}`}
                    strokeWidth={1.9} />
                  

                    <div className="min-w-0 flex-1">
                      <p
                      className={`text-sm truncate ${isProcessable ? 'font-medium text-ink' : 'text-zinc-400 line-through'}`}>
                      
                        {f.name}
                      </p>
                      <p className="text-xs text-zinc-400 truncate flex items-center gap-1">
                        <span>{f.path}</span>
                        <ArrowRight className="w-3 h-3" />
                        <span>{f.size}</span>
                        {f.durationMin ?
                      <span>· {f.durationMin} min</span> :
                      null}
                      </p>
                    </div>

                    {!isProcessable &&
                  <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-400 shrink-0">
                        Skipped
                      </span>
                  }
                  </motion.div>);

            })}
            </div>
          </motion.div>
        }
      </AnimatePresence>
    </div>);

}
