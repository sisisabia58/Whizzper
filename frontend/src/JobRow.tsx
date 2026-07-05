import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Folder,
  ChevronDown,
  Download,
  Loader2,
  Check,
  AlertCircle,
  FileAudio,
  FileVideo,
  FileText } from
'lucide-react';
import { TranscriptJob, jobSummary, statusLabel } from './transcriptions';
import { segmentsToSRT, segmentsToTXT, triggerDownload } from './TranscriptRow';
interface JobRowProps {
  job: TranscriptJob;
  index: number;
}
const statusStyles = {
  completed: {
    icon: Check,
    className: 'bg-ink text-paper border-ink',
    spin: false
  },
  processing: {
    icon: Loader2,
    className: 'bg-paper text-ink border-zinc-300',
    spin: true
  },
  failed: {
    icon: AlertCircle,
    className: 'bg-paper text-zinc-500 border-zinc-200',
    spin: false
  },
  queued: {
    icon: Loader2,
    className: 'bg-paper text-zinc-500 border-zinc-200',
    spin: false
  }
} as const;
export function JobRow({ job, index }: JobRowProps) {
  const [expanded, setExpanded] = useState(false);
  const s = jobSummary(job);
  const rowStatus = s.status;
  const StatusIcon = statusStyles[rowStatus].icon;
  const isProcessing = rowStatus === 'processing';
  const allDone = s.done === s.total && s.processing === 0 && s.queued === 0;

  const downloadAllSRT = (e: React.MouseEvent) => {
    e.stopPropagation(); // Avoid expanding/collapsing row
    const a = document.createElement('a');
    a.href = `/api/task/batch/${job.id}/download`;
    a.download = `${job.folderName}_subtitles.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <motion.div
      initial={{
        opacity: 0,
        y: 12
      }}
      animate={{
        opacity: 1,
        y: 0
      }}
      transition={{
        duration: 0.4,
        delay: index * 0.05,
        ease: 'easeOut'
      }}
      className="border border-zinc-200 rounded-2xl bg-paper overflow-hidden">
      
      {/* Folder header (the "main" job row) */}
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto] gap-4 items-center p-4 md:px-5 md:py-4 text-left hover:bg-paper-off/60 transition-colors">
        
        {/* Left: folder info */}
        <div className="flex items-start gap-4 min-w-0">
          <div className="w-11 h-11 shrink-0 rounded-xl bg-ink text-paper flex items-center justify-center">
            <Folder className="w-5 h-5" strokeWidth={1.9} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-ink truncate">
                {job.folderName}
              </h3>
              <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-zinc-500 border border-zinc-200 rounded-full px-2 py-0.5">
                Drive · {s.total} files
              </span>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
              <span>{s.totalMinutes} min total</span>
              <span className="w-1 h-1 rounded-full bg-zinc-300" />
              <span>{job.language}</span>
              <span className="w-1 h-1 rounded-full bg-zinc-300" />
              <span>{job.createdAt}</span>
            </div>

            {/* Aggregate batch progress */}
            <div className="mt-3 max-w-md">
              <div className="flex items-center justify-between text-xs text-zinc-500 mb-1">
                <span>
                  {allDone ?
                  `${s.completed} completed${s.failed ? `, ${s.failed} failed` : ''}` :
                  `${s.done} of ${s.total} done`}
                </span>
                <span className="font-medium text-ink tabular-nums">
                  {s.progress}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-zinc-200 overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-ink"
                  initial={{
                    width: 0
                  }}
                  animate={{
                    width: `${s.progress}%`
                  }}
                  transition={{
                    duration: 0.8,
                    ease: 'easeOut'
                  }} />
                
              </div>
            </div>
          </div>
        </div>

        {/* Right: status + expand */}
        <div className="flex items-center gap-2 md:justify-end flex-wrap">
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${statusStyles[rowStatus].className}`}>
            
            <StatusIcon
              className={`w-3.5 h-3.5 ${statusStyles[rowStatus].spin ? 'animate-spin' : ''}`}
              strokeWidth={2.5} />
            
            {isProcessing ?
            `Processing ${s.done}/${s.total}` :
            statusLabel[rowStatus]}
          </span>

          {allDone && s.completed > 0 &&
          <button
            onClick={downloadAllSRT}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-ink text-paper text-sm font-semibold hover:opacity-90 transition-opacity"
            title="Download all SRT subtitles in a ZIP file">
            
              <Download className="w-4 h-4" />
              All SRT
            </button>
          }

          <ChevronDown
            className={`w-5 h-5 text-zinc-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          
        </div>
      </button>

      {/* Expanded child files */}
      <AnimatePresence initial={false}>
        {expanded &&
        <motion.div
          initial={{
            height: 0,
            opacity: 0
          }}
          animate={{
            height: 'auto',
            opacity: 1
          }}
          exit={{
            height: 0,
            opacity: 0
          }}
          transition={{
            duration: 0.25
          }}
          className="overflow-hidden">
          
            <ul className="border-t border-zinc-100 divide-y divide-zinc-100">
              {job.files.map((f) => {
              const fs = statusStyles[f.status];
              const FIcon = fs.icon;
              const TypeIcon = f.type === 'video' ? FileVideo : FileAudio;
              
              const handleView = () => {
                if (!f.result) return;
                const txtContent = segmentsToTXT(f.result);
                const txtFilename = f.name.substring(0, f.name.lastIndexOf('.')) + '.txt';
                triggerDownload(txtContent, txtFilename, 'text/plain');
              };
              
              const handleDownload = () => {
                if (!f.result) return;
                const srtContent = segmentsToSRT(f.result);
                const srtFilename = f.name.substring(0, f.name.lastIndexOf('.')) + '.srt';
                triggerDownload(srtContent, srtFilename, 'text/srt');
              };

              return (
                <li
                  key={f.id}
                  className="flex items-center gap-3 px-4 md:px-5 py-3 pl-14 md:pl-16">
                  
                    <TypeIcon
                    className="w-4 h-4 shrink-0 text-zinc-400"
                    strokeWidth={1.9} />
                  
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink truncate">
                        {f.name}
                      </p>
                      {f.status === 'processing' ?
                    <div className="mt-1.5 flex items-center gap-2 max-w-xs">
                          <div className="h-1 flex-1 rounded-full bg-zinc-200 overflow-hidden">
                            <div
                          className="h-full rounded-full bg-ink"
                          style={{
                            width: `${f.progress}%`
                          }} />
                        
                          </div>
                          <span className="text-[11px] text-zinc-500 tabular-nums">
                            {f.progress}%
                          </span>
                        </div> :

                    <p className="text-xs text-zinc-400">
                          {f.durationMin} min
                        </p>
                    }
                    </div>

                    <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium shrink-0 ${fs.className}`}>
                    
                      <FIcon
                      className={`w-3 h-3 ${fs.spin ? 'animate-spin' : ''}`}
                      strokeWidth={2.5} />
                    
                      {statusLabel[f.status]}
                    </span>

                    {f.status === 'completed' &&
                  <div className="hidden sm:flex items-center gap-1 shrink-0">
                        <button
                      onClick={handleView}
                      className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-400 hover:bg-paper-off hover:text-ink transition-colors"
                      aria-label={`View transcript for ${f.name}`}>
                      
                          <FileText className="w-4 h-4" />
                        </button>
                        <button
                      onClick={handleDownload}
                      className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-400 hover:bg-paper-off hover:text-ink transition-colors"
                      aria-label={`Download SRT for ${f.name}`}>
                      
                          <Download className="w-4 h-4" />
                        </button>
                      </div>
                  }
                  </li>);

            })}
            </ul>
          </motion.div>
        }
      </AnimatePresence>
    </motion.div>);

}
