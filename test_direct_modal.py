import os
import sys
import time
import subprocess
import tempfile
import modal

sys.stdout.reconfigure(encoding='utf-8')

VIDEO_PATH = r"C:\Users\wisnu\Downloads\Intro to Replit： Idea to App in 5 minutes 720p30fps 343.mp4"
SRT_PATH = r"C:\Users\wisnu\Downloads\Intro to Replit： Idea to App in 5 minutes 720p30fps 343.srt"

print(f"Reading video file: {VIDEO_PATH}")

# Extract lightweight compressed MP3 audio track using ffmpeg
tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
tmp_mp3 = tmp_file.name
tmp_file.close()

print(f"Compressing audio track to 32k mono MP3 with ffmpeg -> {tmp_mp3}")
cmd = ["ffmpeg", "-y", "-i", VIDEO_PATH, "-vn", "-c:a", "libmp3lame", "-ac", "1", "-b:a", "32k", tmp_mp3]
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

with open(tmp_mp3, "rb") as f:
    audio_bytes = f.read()

os.remove(tmp_mp3)

print(f"Audio payload size: {len(audio_bytes) / 1024 / 1024:.2f} MB")
print("Connecting to Modal serverless GPU function 'run_transcription_gpu' via gRPC stream...")
start_time = time.time()

# Lookup deployed Modal function and call via binary gRPC stream
f = modal.Function.from_name("whizzper-backend", "run_transcription_gpu")
data = f.remote(
    audio_bytes=audio_bytes,
    file_name="audio.mp3",
    model_size="large-v2",
    lang="automatic detection",
    is_translate=False,
    beam_size=5,
    compute_type="float16"
)

wall_time = time.time() - start_time

segments = data.get("segments", [])
elapsed_time = data.get("elapsed_time", 0)

print(f"\nTranscription completed in {elapsed_time:.2f}s (wall time: {wall_time:.2f}s)!")
print(f"Retrieved {len(segments)} segments.")

def format_timestamp(seconds: float) -> str:
    if seconds is None:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

srt_lines = []
for idx, seg in enumerate(segments, 1):
    start_str = format_timestamp(seg.get("start"))
    end_str = format_timestamp(seg.get("end"))
    text = (seg.get("text") or "").strip()
    srt_lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")

srt_content = "\n".join(srt_lines)

with open(SRT_PATH, "w", encoding="utf-8") as f:
    f.write(srt_content)

print(f"\n==========================================")
print(f"SUCCESSFULLY CREATED SRT FILE AT:")
print(f"{SRT_PATH}")
print(f"==========================================\n")
print("--- PREVIEW OF SUBTITLES ---")
print("\n".join(srt_lines[:15]))
