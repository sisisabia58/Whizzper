export type TranscriptStatus = 'completed' | 'processing' | 'queued' | 'failed';

export interface Transcript {
  id: string;
  name: string;
  type: 'audio' | 'video';
  durationMin: number;
  language: string;
  speakers: number;
  createdAt: string;
  status: TranscriptStatus;
  progress: number;
  result?: any;
  error?: string;
}

export interface TranscriptJob {
  id: string;
  folderName: string;
  source: 'google-drive';
  createdAt: string;
  language: string;
  files: Transcript[];
}

export const statusLabel: Record<TranscriptStatus, string> = {
  completed: 'Completed',
  processing: 'Processing',
  queued: 'Queued',
  failed: 'Failed'
};

export function jobSummary(job: TranscriptJob) {
  const total = job.files.length;
  const completed = job.files.filter((f) => f.status === 'completed').length;
  const failed = job.files.filter((f) => f.status === 'failed').length;
  const processing = job.files.filter((f) => f.status === 'processing').length;
  const queued = job.files.filter((f) => f.status === 'queued').length;
  const totalMinutes = job.files.reduce((acc, f) => acc + f.durationMin, 0);
  const progress = Math.round(
    job.files.reduce((acc, f) => acc + f.progress, 0) / Math.max(total, 1)
  );
  const status: TranscriptStatus =
    processing > 0 || queued > 0 ? 'processing' : failed === total ? 'failed' : 'completed';

  return {
    total,
    completed,
    failed,
    processing,
    queued,
    totalMinutes,
    progress,
    status,
    done: completed + failed
  };
}

export interface ScannedFile {
  id: string;
  name: string;
  path: string;
  type: 'audio' | 'video' | 'other';
  size: string;
  durationMin?: number;
}

export const sampleScannedFiles: ScannedFile[] = [
  { id: 's1', name: 'S4E06 — Intro.mp3', path: 'Season 4/Episodes', type: 'audio', size: '48 MB', durationMin: 46 },
  { id: 's2', name: 'S4E07 — Guest.m4a', path: 'Season 4/Episodes', type: 'audio', size: '55 MB', durationMin: 52 },
  { id: 's3', name: 'promo-clip.mp4', path: 'Season 4/Promo', type: 'video', size: '120 MB', durationMin: 3 }
];

export const API_BASE = '/api';

export async function fetchAllTasks(): Promise<Transcript[]> {
  const res = await fetch(`${API_BASE}/task/all`);
  if (!res.ok) throw new Error("Failed to fetch tasks");
  const data = await res.json();
  
  return data.tasks.map((task: any) => {
    const fileName = task.file_name || 'Unnamed Audio';
    const isVideo = fileName.endsWith('.mp4') || fileName.endsWith('.mkv') || fileName.endsWith('.mov');
    
    // Map backend task statuses to frontend statuses
    let status: TranscriptStatus = 'queued';
    if (task.status === 'completed') status = 'completed';
    else if (task.status === 'failed') status = 'failed';
    else if (task.status === 'in_progress') status = 'processing';
    
    return {
      id: task.uuid,
      name: fileName,
      type: isVideo ? 'video' : 'audio',
      durationMin: task.audio_duration ? Math.round(task.audio_duration / 60) : 0,
      language: task.language || 'Auto-detect',
      speakers: task.task_params?.diarization?.diarize ? 2 : 1,
      createdAt: new Date(task.created_at + 'Z').toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }),
      status,
      progress: task.progress ? Math.round(task.progress * 100) : 0,
      result: task.result,
      error: task.error
    };
  });
}

export async function startTranscription(
  file: File,
  preset: 'cheetah' | 'dolphin' | 'whale',
  language: string,
  options: { speakers: boolean; translate: boolean; restore: boolean }
): Promise<string> {
  const formData = new FormData();
  formData.append('file', file);

  // Preset Mapping to parameters
  let modelSize = 'medium';
  let computeType = 'float16';
  if (preset === 'cheetah') {
    modelSize = 'small';
    computeType = 'int8';
  } else if (preset === 'whale') {
    modelSize = 'large-v3';
    computeType = 'float16';
  }

  const queryParams = new URLSearchParams({
    'model_size': modelSize,
    'compute_type': computeType,
    'lang': language === 'Auto-detect' ? 'Auto-detect' : language,
    'is_translate': String(options.translate),
    'vad_filter': String(options.restore),
    'is_diarize': String(options.speakers)
  });

  const res = await fetch(`${API_BASE}/transcription/?${queryParams.toString()}`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error("Failed to queue transcription");
  const data = await res.json();
  return data.identifier;
}
