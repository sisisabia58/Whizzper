import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileAudio,
  FileVideo,
  Download,
  FileText,
  MoreHorizontal,
  Loader2,
  Check,
  AlertCircle,
  Clock } from
'lucide-react';
import { Transcript, statusLabel } from './transcriptions';

const statusStyles: Record<
  Transcript['status'],
  {
    icon: React.ElementType;
    className: string;
    spin?: boolean;
  }> =
{
  completed: {
    icon: Check,
    className: 'bg-ink text-paper border-ink'
  },
  processing: {
    icon: Loader2,
    className: 'bg-paper text-ink border-zinc-300',
    spin: true
  },
  queued: {
    icon: Clock,
    className: 'bg-paper text-zinc-500 border-zinc-200'
  },
  failed: {
    icon: AlertCircle,
    className: 'bg-paper text-zinc-500 border-zinc-200'
  }
};

interface TranscriptRowProps {
  transcript: Transcript;
  index: number;
}

export function segmentsToSRT(segments: any[]): string {
  if (!Array.isArray(segments)) return "";
  return segments.map((seg, idx) => {
    const formatTime = (secs: number) => {
      const h = Math.floor(secs / 3600).toString().padStart(2, '0');
      const m = Math.floor((secs % 3600) / 60).toString().padStart(2, '0');
      const s = Math.floor(secs % 60).toString().padStart(2, '0');
      const ms = Math.floor((secs % 1) * 1000).toString().padStart(3, '0');
      return `${h}:${m}:${s},${ms}`;
    };
    return `${idx + 1}\n${formatTime(seg.start || 0)} --> ${formatTime(seg.end || 0)}\n${seg.text || ''}\n`;
  }).join('\n');
}

export function segmentsToTXT(segments: any[]): string {
  if (!Array.isArray(segments)) return "";
  return segments.map(seg => (seg.text || '').trim()).join('\n');
}

export function triggerDownload(content: string, filename: string, mimeType: string) {
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

export function TranscriptRow({ transcript, index }: TranscriptRowProps) {
  const {
    name,
    type,
    durationMin,
    language,
    speakers,
    createdAt,
    status,
    progress,
    result,
    error
  } = transcript;
  
  const StatusIcon = statusStyles[status].icon;
  const TypeIcon = type === 'video' ? FileVideo : FileAudio;
  const isCompleted = status === 'completed';
  const isProcessing = status === 'processing';

  const downloadSRT = () => {
    if (!result) return;
    const srtContent = segmentsToSRT(result);
    const srtFilename = name.substring(0, name.lastIndexOf('.')) + '.srt';
    triggerDownload(srtContent, srtFilename, 'text/srt');
  };

  const downloadTXT = () => {
    if (!result) return;
    const txtContent = segmentsToTXT(result);
    const txtFilename = name.substring(0, name.lastIndexOf('.')) + '.txt';
    triggerDownload(txtContent, txtFilename, 'text/plain');
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
      className="group grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto] gap-4 items-center p-4 md:px-5 md:py-4 border border-zinc-200 rounded-2xl bg-paper hover:border-zinc-300 transition-colors">
      
      {/* Left: file info */}
      <div className="flex items-start gap-4 min-w-0">
        <div className="w-11 h-11 shrink-0 rounded-xl border border-zinc-200 bg-paper-off flex items-center justify-center text-ink">
          <TypeIcon className="w-5 h-5" strokeWidth={1.9} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-ink truncate" title={name}>{name}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span>{durationMin} min</span>
            <span className="w-1 h-1 rounded-full bg-zinc-300" />
            <span>{language}</span>
            <span className="w-1 h-1 rounded-full bg-zinc-300" />
            <span>
              {speakers} {speakers === 1 ? 'speaker' : 'speakers'}
            </span>
            <span className="w-1 h-1 rounded-full bg-zinc-300" />
            <span>{createdAt}</span>
          </div>

          {isProcessing &&
          <div className="mt-3 max-w-md">
              <div className="flex items-center justify-between text-xs text-zinc-500 mb-1">
                <span>Transcribing…</span>
                <span className="font-medium text-ink tabular-nums">
                  {progress}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-zinc-200 overflow-hidden">
                <motion.div
                className="h-full rounded-full bg-ink"
                initial={{
                  width: 0
                }}
                animate={{
                  width: `${progress}%`
                }}
                transition={{
                  duration: 0.8,
                  ease: 'easeOut'
                }} />
              </div>
            </div>
          }

          {status === 'failed' && error && (
            <p className="mt-2 text-xs text-red-500 font-medium bg-red-50 border border-red-100 rounded-lg p-2 max-w-md">
              Error: {error}
            </p>
          )}
        </div>
      </div>

      {/* Right: status + actions */}
      <div className="flex items-center gap-2 md:justify-end flex-wrap">
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${statusStyles[status].className}`}>
          
          <StatusIcon
            className={`w-3.5 h-3.5 ${statusStyles[status].spin ? 'animate-spin' : ''}`}
            strokeWidth={2.5} />
          
          {statusLabel[status]}
        </span>

        {isCompleted ?
        <div className="flex items-center gap-2">
            <button 
              onClick={downloadTXT}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full border border-zinc-300 text-sm font-medium text-ink hover:bg-paper-off transition-colors"
              title="Download Transcript as TXT"
            >
              <FileText className="w-4 h-4" />
              <span className="hidden sm:inline">TXT</span>
            </button>
            <button 
              onClick={downloadSRT}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.03] active:scale-95"
              title="Download SRT Subtitles"
            >
              <Download className="w-4 h-4" />
              SRT
            </button>
          </div> :
        null}

        <button
          className="w-9 h-9 rounded-full flex items-center justify-center text-zinc-400 hover:bg-paper-off hover:text-ink transition-colors"
          aria-label="More options">
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </div>
    </motion.div>);
}
