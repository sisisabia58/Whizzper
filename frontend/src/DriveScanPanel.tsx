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
  ArrowRight,
  ChevronRight,
  Link as LinkIcon,
  Unlink,
  RefreshCw,
  Settings,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import { ScannedFile, scanDriveFolder } from './transcriptions';

type ScanState = 'idle' | 'scanning' | 'done';
type AccessMode = 'link' | 'connect';

interface DriveConnection {
  connection_id: string;
  account_email: string;
  status: string;
}

interface DriveFolderItem {
  id: string;
  name: string;
}

interface DriveScanPanelProps {
  onSelectionChange: (count: number) => void;
  onFolderChange: (name: string | null) => void;
  onSelectionChangeWithIds?: (
    ids: string[],
    url: string,
    files: { file_id: string; name: string; path: string; parent_id?: string }[],
    extra?: {
      accessMode: AccessMode;
      connectionId?: string;
      writeback?: { enabled: boolean; on_conflict: 'version' | 'skip' };
    }
  ) => void;
}

const typeIcon = {
  audio: FileAudio,
  video: FileVideo,
  other: FileIcon
} as const;

export function DriveScanPanel({
  onSelectionChange,
  onFolderChange,
  onSelectionChangeWithIds
}: DriveScanPanelProps) {
  // Modes & states
  const [accessMode, setAccessMode] = useState<AccessMode>('connect');
  const [link, setLink] = useState('');
  const [state, setState] = useState<ScanState>('idle');
  const [revealed, setRevealed] = useState(0);
  const [scannedFiles, setScannedFiles] = useState<ScannedFile[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const timers = useRef<number[]>([]);

  // Connection list state
  const [connections, setConnections] = useState<DriveConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('');
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [isConnectionsLoading, setIsConnectionsLoading] = useState(false);

  // Folder Explorer state
  const [folderPath, setFolderPath] = useState<{ id: string; name: string }[]>([
    { id: 'root', name: 'My Drive' }
  ]);
  const [currentFolderId, setCurrentFolderId] = useState<string>('root');
  const [subfolders, setSubfolders] = useState<DriveFolderItem[]>([]);
  const [isFoldersLoading, setIsFoldersLoading] = useState(false);
  const [folderSearchQuery, setFolderSearchQuery] = useState('');

  // Writeback state
  const [writebackEnabled, setWritebackEnabled] = useState(true);
  const [writebackConflict, setWritebackConflict] = useState<'version' | 'skip'>('version');

  const processable = scannedFiles.filter((f) => f.type !== 'other');
  const selectedCount = processable.filter((f) => !excluded.has(f.id)).length;

  // Poll/refresh connections
  const fetchConnections = async () => {
    setIsConnectionsLoading(true);
    try {
      const res = await fetch(`/api/drive/connections?owner_key=interim-owner`);
      if (res.ok) {
        const data = await res.json();
        const conns: DriveConnection[] = data.connections || [];
        setConnections(conns);
        if (conns.length > 0 && !selectedConnectionId) {
          setSelectedConnectionId(conns[0].connection_id);
        }
      }
    } catch (e) {
      console.error('Failed to load connections:', e);
    } finally {
      setIsConnectionsLoading(false);
    }
  };

  useEffect(() => {
    fetchConnections();
  }, []);

  // Listen to message events from OAuth callback popup
  useEffect(() => {
    const handleAuthMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === 'google-drive-connected') {
        fetchConnections();
      }
    };
    window.addEventListener('message', handleAuthMessage);
    return () => window.removeEventListener('message', handleAuthMessage);
  }, []);

  // Fetch folders under current active folder
  const fetchSubfolders = async () => {
    if (!selectedConnectionId || accessMode !== 'connect') return;
    setIsFoldersLoading(true);
    try {
      const parentQuery = currentFolderId === 'root' ? '' : `&parent_id=${currentFolderId}`;
      const res = await fetch(`/api/drive/folders?connection_id=${selectedConnectionId}${parentQuery}`);
      if (res.ok) {
        const data = await res.json();
        const files = data.files || [];
        setSubfolders(files.map((f: any) => ({ id: f.id, name: f.name })));
      } else {
        setSubfolders([]);
      }
    } catch (e) {
      console.error('Failed to load folders:', e);
    } finally {
      setIsFoldersLoading(false);
    }
  };

  useEffect(() => {
    fetchSubfolders();
  }, [selectedConnectionId, currentFolderId, accessMode]);

  // Bubble state changes up to TranscribeModal
  useEffect(() => {
    onSelectionChange(state === 'done' ? selectedCount : 0);
    if (state === 'done' && onSelectionChangeWithIds) {
      const activeFiles = processable
        .filter((f) => !excluded.has(f.id))
        .map((f) => ({
          file_id: f.id,
          name: f.name,
          path: (f.path === '/' ? '' : f.path + '/') + f.name,
          parent_id: f.parent_id
        }));
      const activeIds = activeFiles.map((f) => f.file_id);
      
      onSelectionChangeWithIds(activeIds, link, activeFiles, {
        accessMode,
        connectionId: selectedConnectionId || undefined,
        writeback: {
          enabled: writebackEnabled,
          on_conflict: writebackConflict
        }
      });
    }
  }, [
    state,
    selectedCount,
    excluded,
    scannedFiles,
    link,
    accessMode,
    selectedConnectionId,
    writebackEnabled,
    writebackConflict,
    onSelectionChange,
    onSelectionChangeWithIds
  ]);

  useEffect(() => () => timers.current.forEach((t) => clearTimeout(t)), []);

  // Launch OAuth connection popup
  const startOAuthFlow = async () => {
    setIsAuthLoading(true);
    try {
      const res = await fetch(`/api/auth/google/start?owner_key=interim-owner`);
      if (res.ok) {
        const data = await res.json();
        if (data.authorize_url) {
          const w = 600;
          const h = 700;
          const left = window.screen.width / 2 - w / 2;
          const top = window.screen.height / 2 - h / 2;
          window.open(
            data.authorize_url,
            'Connect Google Drive',
            `width=${w},height=${h},top=${top},left=${left}`
          );
        }
      }
    } catch (e) {
      alert('Failed to launch connection flow: ' + String(e));
    } finally {
      setIsAuthLoading(false);
    }
  };

  // Disconnect connection
  const disconnectAccount = async (connId: string) => {
    if (!confirm('Are you sure you want to disconnect this Google Drive account?')) return;
    try {
      const res = await fetch(`/api/drive/connections/${connId}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedConnectionId === connId) {
          setSelectedConnectionId('');
        }
        fetchConnections();
      }
    } catch (e) {
      alert('Failed to disconnect: ' + String(e));
    }
  };

  // Scan folder (either link mode or connect folder selection)
  const startScan = async (folderIdOverride?: string) => {
    setState('scanning');
    setRevealed(0);
    try {
      let result;
      if (accessMode === 'connect') {
        const targetFolderId = folderIdOverride || currentFolderId;
        result = await scanDriveFolder({
          connectionId: selectedConnectionId,
          folderId: targetFolderId
        });
      } else {
        if (!link.trim()) return;
        result = await scanDriveFolder(link);
      }
      onFolderChange(result.folder_name);
      setScannedFiles(result.files);
      setState('done');
      
      // Animate reveal of files
      result.files.forEach((_, i) => {
        const rt = window.setTimeout(() => setRevealed(i + 1), 40 * i);
        timers.current.push(rt);
      });
    } catch (e) {
      alert('Error scanning folder: ' + String(e));
      setState('idle');
    }
  };

  const toggleFile = (id: string) =>
    setExcluded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const totalMinutes = processable
    .filter((f) => !excluded.has(f.id))
    .reduce((acc, f) => acc + (f.durationMin ?? 0), 0);
  const skippedCount = scannedFiles.length - processable.length;

  const filteredFolders = subfolders.filter((f) =>
    f.name.toLowerCase().includes(folderSearchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Mode Switcher */}
      <div className="flex p-0.5 rounded-lg bg-zinc-100 border border-zinc-200 text-xs font-semibold w-fit">
        <button
          onClick={() => {
            setAccessMode('connect');
            setState('idle');
          }}
          className={`px-3 py-1.5 rounded-md transition-all ${
            accessMode === 'connect'
              ? 'bg-white text-ink shadow-sm'
              : 'text-zinc-500 hover:text-ink'
          }`}
        >
          Explore Account
        </button>
        <button
          onClick={() => {
            setAccessMode('link');
            setState('idle');
          }}
          className={`px-3 py-1.5 rounded-md transition-all ${
            accessMode === 'link'
              ? 'bg-white text-ink shadow-sm'
              : 'text-zinc-500 hover:text-ink'
          }`}
        >
          Folder Link Link
        </button>
      </div>

      <AnimatePresence mode="wait">
        {state === 'idle' && (
          <motion.div
            key="setup"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="space-y-5"
          >
            {accessMode === 'link' ? (
              /* Link Mode View */
              <div>
                <label htmlFor="drive-link" className="block text-sm font-semibold text-ink mb-2">
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
                      className="w-full pl-10 pr-4 py-3 rounded-xl border border-zinc-300 bg-paper text-sm text-ink placeholder:text-zinc-400 focus:outline-none focus:border-ink focus:ring-1 focus:ring-ink transition-colors"
                    />
                  </div>
                  <button
                    onClick={() => startScan()}
                    disabled={!link.trim()}
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100 shrink-0"
                  >
                    <Search className="w-4 h-4" />
                    Scan folder
                  </button>
                </div>
                <p className="mt-2 text-xs text-zinc-500">
                  We recursively scan the folder and all subfolders, then queue only audio & video files.
                </p>
              </div>
            ) : (
              /* Connect Mode View */
              <div className="space-y-4">
                {connections.length === 0 ? (
                  /* Connect Callout */
                  <div className="rounded-2xl border border-zinc-200 bg-white p-6 text-center space-y-4">
                    <div className="w-12 h-12 rounded-full bg-zinc-50 border border-zinc-100 flex items-center justify-center mx-auto text-zinc-500">
                      <FolderOpen className="w-6 h-6" />
                    </div>
                    <div className="space-y-1.5">
                      <h4 className="text-sm font-bold text-ink">Connect Google Drive</h4>
                      <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                        Link your Google account to dynamically select folders, browse Shared drives, and automatically write SRT subtitles back.
                      </p>
                    </div>
                    <button
                      onClick={startOAuthFlow}
                      disabled={isAuthLoading}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-50"
                    >
                      {isAuthLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <FolderOpen className="w-4 h-4" />
                      )}
                      Connect Account
                    </button>
                  </div>
                ) : (
                  /* Explorer Panel */
                  <div className="space-y-4">
                    {/* Active Account Header */}
                    <div className="flex items-center justify-between p-3 rounded-xl border border-zinc-200 bg-zinc-50/50">
                      <div className="flex items-center gap-2 min-w-0">
                        <FolderOpen className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span className="text-xs font-bold text-ink truncate">
                          {connections.find((c) => c.connection_id === selectedConnectionId)
                            ?.account_email || 'Linked Account'}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={startOAuthFlow}
                          title="Add another account"
                          className="p-1.5 rounded-lg hover:bg-zinc-200 text-zinc-600 transition-colors"
                        >
                          <ChevronRight className="w-4 h-4 rotate-90" />
                        </button>
                        <button
                          onClick={() => disconnectAccount(selectedConnectionId)}
                          title="Disconnect account"
                          className="p-1.5 rounded-lg hover:bg-red-50 text-red-600 transition-colors"
                        >
                          <Unlink className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {/* Folder Explorer Breadcrumb */}
                    <div className="flex items-center gap-1 overflow-x-auto py-1 text-xs text-zinc-500 font-semibold scrollbar-none">
                      {folderPath.map((item, idx) => (
                        <React.Fragment key={item.id}>
                          {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-zinc-300 shrink-0" />}
                          <button
                            onClick={() => {
                              setFolderPath(folderPath.slice(0, idx + 1));
                              setCurrentFolderId(item.id);
                            }}
                            className={`hover:text-ink shrink-0 ${
                              idx === folderPath.length - 1 ? 'text-ink font-bold' : ''
                            }`}
                          >
                            {item.name}
                          </button>
                        </React.Fragment>
                      ))}
                    </div>

                    {/* Folder Directory Explorer */}
                    <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden flex flex-col h-64">
                      {/* Explorer Toolbar */}
                      <div className="border-b border-zinc-100 px-3 py-2 flex items-center justify-between gap-2">
                        <div className="relative flex-1">
                          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" />
                          <input
                            type="search"
                            value={folderSearchQuery}
                            onChange={(e) => setFolderSearchQuery(e.target.value)}
                            placeholder="Filter folders…"
                            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-zinc-50 text-xs placeholder:text-zinc-400 border border-zinc-100 focus:outline-none focus:border-ink transition-colors"
                          />
                        </div>
                        <button
                          onClick={fetchSubfolders}
                          title="Refresh current folder"
                          className="p-1.5 rounded-lg border border-zinc-100 hover:bg-zinc-50 text-zinc-500 transition-colors shrink-0"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {/* Folder Listing */}
                      <div className="flex-1 overflow-y-auto divide-y divide-zinc-50">
                        {isFoldersLoading ? (
                          <div className="h-full flex items-center justify-center text-zinc-400 text-xs gap-2">
                            <Loader2 className="w-4 h-4 animate-spin text-ink" />
                            Loading folders…
                          </div>
                        ) : filteredFolders.length === 0 ? (
                          <div className="h-full flex flex-col items-center justify-center p-6 text-center text-zinc-400">
                            <Folder className="w-8 h-8 text-zinc-200 mb-1.5" />
                            <p className="text-xs">No subfolders found</p>
                          </div>
                        ) : (
                          filteredFolders.map((f) => (
                            <div
                              key={f.id}
                              className="flex items-center justify-between gap-3 px-4 py-2 hover:bg-zinc-50 transition-colors"
                            >
                              <button
                                onClick={() => {
                                  setFolderPath([...folderPath, { id: f.id, name: f.name }]);
                                  setCurrentFolderId(f.id);
                                }}
                                className="flex items-center gap-2.5 text-xs text-ink font-semibold text-left min-w-0 flex-1 py-1"
                              >
                                <Folder className="w-4 h-4 text-zinc-400 shrink-0" />
                                <span className="truncate">{f.name}</span>
                              </button>
                              <button
                                onClick={() => startScan(f.id)}
                                className="px-2.5 py-1 rounded bg-zinc-100 text-[10px] font-bold text-ink hover:bg-ink hover:text-white transition-colors uppercase tracking-wider"
                              >
                                Scan
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {/* SRT Write-Back Options */}
                    <div className="rounded-xl border border-zinc-200 p-4 space-y-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-0.5">
                          <label className="text-xs font-bold text-ink cursor-pointer" htmlFor="wb-toggle">
                            Automatic SRT Write-Back
                          </label>
                          <p className="text-[10px] text-zinc-500">
                            Save transcription outputs directly back into this Google Drive folder automatically.
                          </p>
                        </div>
                        <input
                          id="wb-toggle"
                          type="checkbox"
                          checked={writebackEnabled}
                          onChange={(e) => setWritebackEnabled(e.target.checked)}
                          className="mt-0.5 w-4 h-4 rounded border-zinc-300 text-ink focus:ring-ink"
                        />
                      </div>

                      {writebackEnabled && (
                        <div className="pt-2.5 border-t border-zinc-100 flex items-center justify-between gap-4">
                          <span className="text-[11px] font-semibold text-zinc-500">
                            Conflict Resolution:
                          </span>
                          <select
                            value={writebackConflict}
                            onChange={(e) => setWritebackConflict(e.target.value as any)}
                            className="text-xs bg-paper border border-zinc-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-ink"
                          >
                            <option value="version">Create Version (file_v2.srt)</option>
                            <option value="skip">Skip Upload</option>
                          </select>
                        </div>
                      )}
                    </div>

                    {/* Scan Action */}
                    <div className="pt-2 flex items-center gap-2">
                      <button
                        onClick={() => startScan()}
                        className="flex-1 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.01] active:scale-[0.98]"
                      >
                        <Search className="w-4 h-4" />
                        Scan Current Folder ({folderPath[folderPath.length - 1].name})
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* Scanning state */}
        {state === 'scanning' && (
          <motion.div
            key="scanning"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="rounded-2xl border border-zinc-200 bg-paper-off p-8 flex flex-col items-center text-center"
          >
            <div className="relative w-12 h-12 mb-4">
              <Folder className="w-12 h-12 text-zinc-300" strokeWidth={1.5} />
              <Loader2 className="absolute inset-0 m-auto w-5 h-5 text-ink animate-spin" />
            </div>
            <p className="font-display font-bold text-ink">Scanning folder recursively…</p>
            <p className="text-sm text-zinc-500 mt-1 tabular-nums">Items discovered...</p>
          </motion.div>
        )}

        {/* Result state */}
        {state === 'done' && (
          <motion.div
            key="done"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                Scanned Results
              </span>
              <button
                onClick={() => setState('idle')}
                className="text-xs font-semibold text-zinc-500 hover:text-ink flex items-center gap-1"
              >
                <ArrowRight className="w-3.5 h-3.5 rotate-180" />
                Change Folder
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-zinc-200 bg-paper-off px-4 py-3 text-sm">
              <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
                <Check className="w-4 h-4 text-emerald-600" />
                {selectedCount} files to transcribe
              </span>
              <span className="text-zinc-300">·</span>
              <span className="text-zinc-500 tabular-nums">{totalMinutes} min total</span>
              <span className="text-zinc-300">·</span>
              <span className="text-zinc-500">{skippedCount} skipped</span>
            </div>

            <div
              className="max-h-60 overflow-y-auto rounded-xl border border-zinc-200 divide-y divide-zinc-100"
              role="list"
              aria-label="Scanned files"
            >
              {scannedFiles.slice(0, revealed).map((f: ScannedFile) => {
                const Icon = typeIcon[f.type];
                const isProcessable = f.type !== 'other';
                const included = isProcessable && !excluded.has(f.id);
                return (
                  <motion.div
                    key={f.id}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    role="listitem"
                    className={`flex items-center gap-3 px-4 py-2.5 ${
                      isProcessable ? 'bg-paper' : 'bg-paper-off/60'
                    }`}
                  >
                    {isProcessable ? (
                      <button
                        onClick={() => toggleFile(f.id)}
                        role="checkbox"
                        aria-checked={included}
                        aria-label={`${included ? 'Exclude' : 'Include'} ${f.name}`}
                        className={`w-5 h-5 shrink-0 rounded-md border flex items-center justify-center transition-colors ${
                          included ? 'bg-ink border-ink text-paper' : 'bg-paper border-zinc-300'
                        }`}
                      >
                        {included && (
                          <svg
                            viewBox="0 0 12 12"
                            className="w-3 h-3"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2.5}
                          >
                            <path
                              d="M2.5 6.5L5 9l4.5-5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        )}
                      </button>
                    ) : (
                      <span className="w-5 h-5 shrink-0" aria-hidden="true" />
                    )}

                    <Icon
                      className={`w-4 h-4 shrink-0 ${
                        isProcessable ? 'text-ink' : 'text-zinc-300'
                      }`}
                      strokeWidth={1.9}
                    />

                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-xs truncate ${
                          isProcessable ? 'font-semibold text-ink' : 'text-zinc-400 line-through'
                        }`}
                      >
                        {f.name}
                      </p>
                      <p className="text-[10px] text-zinc-400 truncate flex items-center gap-1">
                        <span>{f.path}</span>
                        <ArrowRight className="w-2.5 h-2.5 text-zinc-300" />
                        <span>{f.size}</span>
                        {f.durationMin ? <span>· {f.durationMin} min</span> : null}
                      </p>
                    </div>

                    {!isProcessable && (
                      <span className="text-[9px] font-bold uppercase tracking-wider text-zinc-400 shrink-0 bg-zinc-100 px-1.5 py-0.5 rounded">
                        Skipped
                      </span>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
