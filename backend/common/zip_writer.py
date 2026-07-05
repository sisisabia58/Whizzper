import io
import zipfile
from typing import List
from backend.db.task.models import Task

def create_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def compile_srt(segments: List[dict]) -> str:
    srt_lines = []
    for idx, seg in enumerate(segments, 1):
        start = create_srt_time(seg.get("start", 0.0))
        end = create_srt_time(seg.get("end", 0.0))
        text = seg.get("text", "").strip()
        srt_lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(srt_lines)

def build_srt_zip(tasks: List[Task]) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for task in tasks:
            if task.status == "completed" and task.result:
                srt_content = compile_srt(task.result)
                filename = task.file_name or f"{task.uuid}.srt"
                if not filename.endswith(".srt"):
                    filename = f"{filename}.srt"
                # Use source path to structure within the ZIP file
                zip_path = task.source_path or filename
                zip_file.writestr(zip_path, srt_content)
    return zip_buffer.getvalue()
