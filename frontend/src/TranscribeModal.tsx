import React, { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  UploadCloud,
  Link2,
  ChevronDown,
  Zap,
  Scale,
  Sparkles,
  Users,
  Languages,
  Wand2,
  ChevronUp,
  FileAudio,
  HardDriveUpload,
  FolderOpen,
  Loader2 } from
'lucide-react';
import { Waveform } from './Waveform';
import { DriveScanPanel } from './DriveScanPanel';
import { startTranscription, startBatchTranscription } from './transcriptions';

interface TranscribeModalProps {
  open: boolean;
  onClose: () => void;
}
type ModelId = 'cheetah' | 'dolphin' | 'whale';
type SourceMode = 'upload' | 'drive';

const models: {
  id: ModelId;
  name: string;
  tagline: string;
  icon: React.ElementType;
}[] = [
{
  id: 'cheetah',
  name: 'Cheetah',
  tagline: 'Fastest',
  icon: Zap
},
{
  id: 'dolphin',
  name: 'Dolphin',
  tagline: 'Balanced',
  icon: Scale
},
{
  id: 'whale',
  name: 'Whale',
  tagline: 'Most accurate',
  icon: Sparkles
}];

const languages = [
  'Auto-detect',
  'English',
  'Spanish',
  'French',
  'German',
  'Portuguese',
  'Japanese',
  'Mandarin'
];

const advancedOptions: {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
}[] = [
{
  id: 'speakers',
  label: 'Recognize speakers',
  description: 'Labels each section of the transcript with who is speaking.',
  icon: Users
},
{
  id: 'translate',
  label: 'Transcribe to English',
  description: 'Transcribe the original audio language directly to English.',
  icon: Languages
},
{
  id: 'restore',
  label: 'Restore audio',
  description:
  'Use AI to remove background noise and enhance speech. Best for poor-quality files.',
  icon: Wand2
}];

export function TranscribeModal({ open, onClose }: TranscribeModalProps) {
  const [sourceMode, setSourceMode] = useState<SourceMode>('upload');
  const [model, setModel] = useState<ModelId>('dolphin');
  const [language, setLanguage] = useState('Auto-detect');
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    speakers: true,
    translate: false,
    restore: false
  });
  
  const [selectedRealFile, setSelectedRealFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [driveCount, setDriveCount] = useState(0);
  const [driveFolder, setDriveFolder] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<{ file_id: string; name: string; path: string }[]>([]);
  const [folderUrl, setFolderUrl] = useState('');
  const [driveExtraParams, setDriveExtraParams] = useState<{
    accessMode?: 'link' | 'connect';
    connectionId?: string;
    writeback?: { enabled: boolean; on_conflict: 'version' | 'skip' };
  }>({});

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      setSelectedRealFile(null);
      setIsSubmitting(false);
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose, isSubmitting]);

  const toggle = (id: string) =>
    setToggles((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedRealFile(e.target.files[0]);
    }
  };

  const triggerBrowse = (e: React.MouseEvent) => {
    e.preventDefault();
    fileInputRef.current?.click();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedRealFile(e.dataTransfer.files[0]);
    }
  };

  const handleTranscribeSubmit = async () => {
    if (sourceMode === 'upload' && !selectedRealFile) return;
    if (sourceMode === 'drive' && selectedFiles.length === 0) return;
    
    setIsSubmitting(true);
    try {
      if (sourceMode === 'upload' && selectedRealFile) {
        await startTranscription(
          selectedRealFile,
          model,
          language,
          {
            speakers: toggles.speakers,
            translate: toggles.translate,
            restore: toggles.restore
          }
        );
      } else if (sourceMode === 'drive') {
        await startBatchTranscription(
          folderUrl,
          driveFolder || "Google Drive Folder",
          selectedFiles,
          model,
          language,
          {
            speakers: toggles.speakers,
            translate: toggles.translate,
            restore: toggles.restore
          },
          driveExtraParams
        );
      }
      onClose();
    } catch (e) {
      alert("Error submitting transcription task: " + String(e));
    } finally {
      setIsSubmitting(false);
    }
  };

  const readyToSubmit = (sourceMode === 'upload' ? !!selectedRealFile : driveCount > 0) && !isSubmitting;
  
  const submitLabel = isSubmitting 
    ? 'Uploading & queueing...' 
    : sourceMode === 'upload' 
      ? selectedRealFile 
        ? 'Transcribe' 
        : 'Add a file to transcribe' 
      : driveCount > 0 
        ? `Transcribe ${driveCount} ${driveCount === 1 ? 'file' : 'files'}` 
        : 'Scan a folder to continue';

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => { if (!isSubmitting) onClose(); }}
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
            aria-hidden="true"
          />

          {/* Dialog */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="transcribe-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto bg-paper rounded-3xl border border-zinc-200 shadow-[0_40px_80px_-24px_rgba(0,0,0,0.35)]"
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 px-6 py-5 bg-paper/90 backdrop-blur-md border-b border-zinc-200">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-ink text-paper flex items-center justify-center">
                  <UploadCloud className="w-4.5 h-4.5" strokeWidth={2.2} />
                </div>
                <h2 id="transcribe-title" className="text-xl font-display font-extrabold tracking-tight">
                  New transcription
                </h2>
              </div>
              <button
                onClick={onClose}
                disabled={isSubmitting}
                aria-label="Close dialog"
                className="w-9 h-9 rounded-full flex items-center justify-center text-zinc-400 hover:bg-paper-off hover:text-ink transition-colors disabled:opacity-35"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 py-6 space-y-7">
              {/* Source mode tabs */}
              <div
                role="tablist"
                aria-label="Source"
                className="grid grid-cols-2 gap-1 p-1 rounded-2xl bg-paper-off border border-zinc-200"
              >
                {[
                  { id: 'upload' as const, label: 'Upload files', icon: HardDriveUpload },
                  { id: 'drive' as const, label: 'Google Drive folder', icon: FolderOpen }
                ].map((tab) => {
                  const active = sourceMode === tab.id;
                  return (
                    <button
                      key={tab.id}
                      role="tab"
                      aria-selected={active}
                      disabled={isSubmitting}
                      onClick={() => setSourceMode(tab.id)}
                      className={`relative flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 ${
                        active ? 'text-paper' : 'text-zinc-600 hover:text-ink'
                      }`}
                    >
                      {active && (
                        <motion.span
                          layoutId="internal-source-tab"
                          className="absolute inset-0 rounded-xl bg-ink"
                          transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                        />
                      )}
                      <tab.icon className="relative w-4 h-4" strokeWidth={2} />
                      <span className="relative">{tab.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Source content */}
              <AnimatePresence mode="wait">
                {sourceMode === 'upload' ? (
                  <motion.section
                    key="upload"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-semibold text-ink">
                        Audio / video file
                      </label>
                    </div>

                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept="audio/*,video/*"
                      style={{ display: 'none' }}
                      disabled={isSubmitting}
                    />

                    <button
                      onClick={triggerBrowse}
                      onDragOver={handleDragOver}
                      onDrop={handleDrop}
                      disabled={isSubmitting}
                      className="group w-full rounded-2xl border-2 border-dashed border-zinc-300 bg-paper-off hover:border-ink hover:bg-white transition-colors px-6 py-8 flex flex-col items-center justify-center text-center cursor-pointer disabled:opacity-60 disabled:hover:bg-paper-off"
                    >
                      {selectedRealFile ? (
                        <>
                          <div className="w-12 h-12 rounded-xl bg-ink text-paper flex items-center justify-center mb-3">
                            <FileAudio className="w-5 h-5" />
                          </div>
                          <p className="font-semibold text-ink px-4 break-all">{selectedRealFile.name}</p>
                          <p className="text-xs text-zinc-500 mt-1">
                            {(selectedRealFile.size / (1024 * 1024)).toFixed(2)} MB · Click to choose a different file
                          </p>
                        </>
                      ) : (
                        <>
                          <div className="h-8 mb-3 w-32">
                            <Waveform bars={20} barWidth={3} gap={3} minHeight={3} maxHeight={28} className="h-full" />
                          </div>
                          <p className="font-display font-bold text-lg text-ink">
                            Drag &amp; drop
                          </p>
                          <p className="text-xs text-zinc-500 mt-1 max-w-xs">
                            MP3, MP4, M4A, MOV, AAC, WAV, OGG, OPUS, MPEG, WMA, WMV
                          </p>
                          <span className="my-3 text-xs text-zinc-400">— or —</span>
                          <span className="inline-flex items-center px-4 py-2 rounded-full bg-ink text-paper text-sm font-semibold transition-transform group-hover:scale-[1.03] group-disabled:scale-100">
                            Browse files
                          </span>
                        </>
                      )}
                    </button>
                  </motion.section>
                ) : (
                  <motion.section
                    key="drive"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.2 }}
                  >
                    <DriveScanPanel
                      onSelectionChange={setDriveCount}
                      onFolderChange={setDriveFolder}
                      onSelectionChangeWithIds={(ids, url, files, extra) => {
                        setSelectedFiles(files || []);
                        setFolderUrl(url);
                        setDriveExtraParams(extra || {});
                      }}
                    />
                  </motion.section>
                )}
              </AnimatePresence>

              <div className="pt-1 border-t border-zinc-100" />

              {/* Language */}
              <section>
                <label htmlFor="internal-audio-language" className="block text-sm font-semibold text-ink mb-2">
                  Audio language
                </label>
                <div className="relative">
                  <select
                    id="internal-audio-language"
                    value={language}
                    disabled={isSubmitting}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full appearance-none rounded-xl border border-zinc-300 bg-paper px-4 py-3 text-sm font-medium text-ink focus:outline-none focus:border-ink focus:ring-1 focus:ring-ink transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {languages.map((lang) => (
                      <option key={lang} value={lang}>
                        {lang}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                </div>
              </section>

              {/* Transcription mode */}
              <section>
                <span className="block text-sm font-semibold text-ink mb-2">
                  Transcription mode
                </span>
                <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Transcription mode">
                  {models.map((m) => {
                    const active = model === m.id;
                    return (
                      <button
                        key={m.id}
                        role="radio"
                        aria-checked={active}
                        disabled={isSubmitting}
                        onClick={() => setModel(m.id)}
                        className={`relative flex flex-col items-center text-center gap-1 rounded-2xl border px-3 py-4 transition-all disabled:opacity-50 ${
                          active
                            ? 'border-ink bg-ink text-paper'
                            : 'border-zinc-200 bg-paper text-ink hover:border-zinc-300'
                        }`}
                      >
                        <m.icon className={`w-5 h-5 mb-0.5 ${active ? 'text-paper' : 'text-zinc-500'}`} strokeWidth={2} />
                        <span className="font-semibold text-sm">{m.name}</span>
                        <span className={`text-xs ${active ? 'text-zinc-300' : 'text-zinc-500'}`}>{m.tagline}</span>
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* Advanced settings */}
              <section>
                <button
                  onClick={() => setShowAdvanced((v) => !v)}
                  aria-expanded={showAdvanced}
                  disabled={isSubmitting}
                  className="flex items-center gap-2 text-sm font-semibold text-ink hover:text-zinc-600 transition-colors disabled:opacity-50"
                >
                  <Users className="w-4 h-4" />
                  Speaker recognition &amp; more settings
                  {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                <AnimatePresence initial={false}>
                  {showAdvanced && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-4 grid sm:grid-cols-1 gap-2">
                        {advancedOptions.map((opt) => {
                          const checked = toggles[opt.id];
                          return (
                            <button
                              key={opt.id}
                              disabled={isSubmitting}
                              onClick={() => toggle(opt.id)}
                              role="checkbox"
                              aria-checked={checked}
                              className={`w-full flex items-start gap-3 text-left rounded-2xl border px-4 py-3 transition-colors disabled:opacity-50 ${
                                checked
                                  ? 'border-ink bg-paper-off'
                                  : 'border-zinc-200 bg-paper hover:border-zinc-300'
                              }`}
                            >
                              <span
                                className={`mt-0.5 w-5 h-5 shrink-0 rounded-md border flex items-center justify-center transition-colors ${
                                  checked ? 'bg-ink border-ink text-paper' : 'bg-paper border-zinc-300'
                                }`}
                              >
                                {checked && (
                                  <svg viewBox="0 0 12 12" className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5}>
                                    <path d="M2.5 6.5L5 9l4.5-5" strokeLinecap="round" strokeLinejoin="round" />
                                  </svg>
                                )}
                              </span>
                              <span className="min-w-0">
                                <span className="flex items-center gap-1.5 font-semibold text-sm text-ink">
                                  <opt.icon className="w-3.5 h-3.5 text-zinc-500" />
                                  {opt.label}
                                </span>
                                <span className="block text-xs text-zinc-500 mt-0.5">{opt.description}</span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </section>
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 px-6 py-4 bg-paper/90 backdrop-blur-md border-t border-zinc-200 flex items-center gap-4">
              {sourceMode === 'drive' && driveFolder && driveCount > 0 && (
                <p className="hidden sm:flex items-center gap-1.5 text-sm text-zinc-500 min-w-0">
                  <FolderOpen className="w-4 h-4 shrink-0" />
                  <span className="truncate">
                    Batch from <span className="font-medium text-ink">{driveFolder}</span>
                  </span>
                </p>
              )}
              {isSubmitting && (
                <Loader2 className="animate-spin w-5 h-5 text-ink shrink-0" />
              )}
              <button
                disabled={!readyToSubmit}
                onClick={handleTranscribeSubmit}
                className="ml-auto w-full sm:w-auto sm:min-w-[220px] py-3.5 px-6 rounded-full bg-ink text-paper font-semibold transition-transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                {submitLabel}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
