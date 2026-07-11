import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { AudioLines, Upload, Search, Files, CircleCheck, Loader2, Hourglass, ServerCog } from 'lucide-react';
import { InternalSidebar } from './InternalSidebar';
import { TranscriptRow } from './TranscriptRow';
import { TranscribeModal } from './TranscribeModal';
import { Transcript, fetchAllTasks, groupTranscripts } from './transcriptions';
import { JobRow } from './JobRow';

export function Internal() {
  const PAGE_LIMIT = 15;
  const [transcriptsList, setTranscriptsList] = useState<Transcript[]>([]);
  const [totalTasks, setTotalTasks] = useState(0);
  const [filter, setFilter] = useState<'all' | 'completed' | 'processing' | 'queued' | 'failed'>('all');
  const [query, setQuery] = useState('');
  const [transcribeOpen, setTranscribeOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = async (append = false) => {
    try {
      const currentOffset = append ? transcriptsList.length : 0;
      const { tasks, total } = await fetchAllTasks(PAGE_LIMIT, currentOffset);
      if (append) {
        setTranscriptsList((prev) => {
          const existingIds = new Set(prev.map((t) => t.id));
          const newTasks = tasks.filter((t) => !existingIds.has(t.id));
          return [...prev, ...newTasks];
        });
      } else {
        setTranscriptsList(tasks);
      }
      setTotalTasks(total);
    } catch (e) {
      console.error("Error loading task data:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData(false);
  }, []);

  useEffect(() => {
    const eventSource = new EventSource('/api/task/stream');
    
    eventSource.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        if (update.type === 'task_updated') {
          setTranscriptsList((prev) => {
            const exists = prev.some((t) => t.id === update.uuid);
            if (!exists) {
              fetchAllTasks(PAGE_LIMIT, 0).then(({ tasks, total }) => {
                setTranscriptsList(tasks);
                setTotalTasks(total);
              }).catch((e) => console.error("Error reloading tasks on SSE update:", e));
              return prev;
            }
            return prev.map((t) => {
              if (t.id === update.uuid) {
                let status = t.status;
                if (update.status === 'completed') status = 'completed';
                else if (update.status === 'failed') status = 'failed';
                else if (update.status === 'in_progress') status = 'processing';
                
                return {
                  ...t,
                  status,
                  progress: update.progress ? Math.round(update.progress * 100) : 0
                };
              }
              return t;
            });
          });
        }
      } catch (err) {
        console.error("Failed to parse SSE event data:", err);
      }
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const handleDeleteTask = (id: string) => {
    setTranscriptsList((prev) => prev.filter((t) => t.id !== id));
    setTotalTasks((prev) => Math.max(0, prev - 1));
  };

  const visible = transcriptsList.filter((t) => {
    const matchesFilter = filter === 'all' || t.status === filter;
    const matchesQuery = t.name.toLowerCase().includes(query.toLowerCase());
    return matchesFilter && matchesQuery;
  });

  const allFiles = [...transcriptsList];

  const summary = [
    { label: 'Total jobs', value: String(allFiles.length), icon: Files },
    { label: 'Completed', value: String(allFiles.filter((t) => t.status === 'completed').length), icon: CircleCheck },
    { label: 'Processing', value: String(allFiles.filter((t) => t.status === 'processing').length), icon: Loader2 },
    { label: 'Minutes processed', value: allFiles.reduce((acc, t) => acc + t.durationMin, 0).toLocaleString(), icon: AudioLines }
  ];

  const filters: { key: 'all' | 'completed' | 'processing' | 'queued' | 'failed'; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'completed', label: 'Completed' },
    { key: 'processing', label: 'Processing' },
    { key: 'queued', label: 'Queued' },
    { key: 'failed', label: 'Failed' }
  ];

  return (
    <div className="min-h-screen w-full bg-paper-off text-ink font-sans antialiased flex">
      <InternalSidebar />

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-30 bg-paper/80 backdrop-blur-md border-b border-zinc-200">
          <div className="px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 lg:hidden">
              <AudioLines className="w-6 h-6 text-ink" strokeWidth={2.2} />
              <span className="text-lg font-display font-extrabold tracking-tight">
                Whizzper
              </span>
            </div>

            {/* Search */}
            <div className="relative flex-1 max-w-md ml-auto lg:ml-0">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search jobs…"
                aria-label="Search jobs"
                className="w-full pl-9 pr-4 py-2 rounded-full bg-paper-off border border-zinc-200 text-sm placeholder:text-zinc-400 focus:outline-none focus:border-ink focus:ring-1 focus:ring-ink transition-colors"
              />
            </div>

            <button
              onClick={() => setTranscribeOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-ink text-paper text-sm font-semibold transition-transform hover:scale-[1.03] active:scale-95 shrink-0"
            >
              <Upload className="w-4 h-4" />
              <span className="hidden sm:inline">New transcription</span>
            </button>
          </div>
        </header>

        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-8 max-w-6xl w-full mx-auto">
          {/* Heading */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mb-8"
          >
            <div className="inline-flex items-center gap-1.5 mb-3 px-2.5 py-1 rounded-full border border-zinc-300 bg-paper text-xs font-semibold uppercase tracking-wider text-zinc-500">
              <ServerCog className="w-3.5 h-3.5" />
              Internal console
            </div>
            <h1 className="text-3xl md:text-4xl font-display font-extrabold tracking-tight">
              Transcription queue
            </h1>
            <p className="text-zinc-500 mt-1">
              Upload files, monitor progress, and download transcripts. No account or billing required.
            </p>
          </motion.div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
            {summary.map((card, index) => (
              <motion.div
                key={card.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.06 }}
                className="p-5 rounded-2xl border border-zinc-200 bg-paper"
              >
                <card.icon className="w-5 h-5 text-zinc-400 mb-3" strokeWidth={1.9} />
                <div className="text-3xl font-display font-extrabold tracking-tight tabular-nums">
                  {card.value}
                </div>
                <div className="text-sm text-zinc-500 mt-0.5">{card.label}</div>
              </motion.div>
            ))}
          </div>

          {/* Section header + filters */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">
            <h2 className="text-xl font-display font-bold">Jobs</h2>
            <div className="flex items-center gap-1.5 overflow-x-auto -mx-1 px-1">
              {filters.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setFilter(f.key)}
                  aria-pressed={filter === f.key}
                  className={`px-3.5 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                    filter === f.key
                      ? 'bg-ink text-paper'
                      : 'text-zinc-600 hover:bg-paper border border-zinc-200'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="flex flex-col gap-3">
            {isLoading ? (
              <div className="text-center py-16">
                <Loader2 className="animate-spin w-8 h-8 text-zinc-400 mx-auto" />
              </div>
            ) : visible.length > 0 ? (
              groupTranscripts(visible).map((item, index) => {
                if (item.type === 'batch') {
                  return <JobRow key={item.id} job={item.item} index={index} />;
                } else {
                  return <TranscriptRow key={item.id} transcript={item.item} index={index} onDelete={handleDeleteTask} />;
                }
              })
            ) : (
              <div className="text-center py-16 border border-dashed border-zinc-300 rounded-2xl bg-paper">
                <Hourglass className="w-8 h-8 text-zinc-300 mx-auto mb-3" />
                <p className="font-semibold text-ink">No jobs found</p>
                <p className="text-sm text-zinc-500 mt-1">
                  Try a different filter or upload a new file.
                </p>
              </div>
            )}

            {transcriptsList.length < totalTasks && (
              <button
                onClick={() => loadData(true)}
                className="mt-6 px-5 py-2.5 border border-zinc-200 bg-paper text-zinc-600 rounded-full text-xs font-semibold uppercase tracking-wider hover:bg-paper-off hover:text-ink transition-colors mx-auto flex items-center justify-center shadow-sm"
              >
                Load More
              </button>
            )}
          </div>
        </main>
      </div>

      <TranscribeModal
        open={transcribeOpen}
        onClose={() => {
          setTranscribeOpen(false);
          loadData(false);
        }}
      />
    </div>
  );
}
