from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from backend.db.db_instance import get_db_session
from backend.db.task.models import Task
from backend.db.share.models import TranscriptShareToken, generate_share_token

share_router = APIRouter(tags=["Transcript Share"])

def find_task_by_id_or_uuid(db: Session, identifier: str) -> Optional[Task]:
    task = db.exec(select(Task).where(Task.uuid == identifier)).first()
    if not task and identifier.isdigit():
        task = db.exec(select(Task).where(Task.id == int(identifier))).first()
    return task

@share_router.post("/api/transcripts/{task_uuid}/share")
def create_share_token(
    task_uuid: str,
    expires_in_hours: Optional[int] = 72,
    db: Session = Depends(get_db_session)
):
    task = find_task_by_id_or_uuid(db, task_uuid)
    if not task:
        raise HTTPException(status_code=404, detail="Transcript task not found")
    
    target_uuid = task.uuid or str(task.id)
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None
    
    # Reuse existing active token if present
    existing = db.exec(
        select(TranscriptShareToken)
        .where(TranscriptShareToken.task_uuid == target_uuid)
        .where(TranscriptShareToken.revoked_at == None)
    ).all()
    
    for tok in existing:
        if tok.is_valid():
            return {
                "token": tok.token,
                "share_url": f"/transcripts/share/{tok.token}",
                "expires_at": tok.expires_at.isoformat() if tok.expires_at else None
            }

    share_token = TranscriptShareToken(
        token=generate_share_token(),
        task_uuid=target_uuid,
        expires_at=expires_at,
        created_at=datetime.utcnow()
    )
    db.add(share_token)
    db.commit()
    db.refresh(share_token)

    return {
        "token": share_token.token,
        "share_url": f"/transcripts/share/{share_token.token}",
        "expires_at": share_token.expires_at.isoformat() if share_token.expires_at else None
    }

@share_router.delete("/api/transcripts/{task_uuid}/share/{token}")
def revoke_share_token(task_uuid: str, token: str, db: Session = Depends(get_db_session)):
    task = find_task_by_id_or_uuid(db, task_uuid)
    target_uuid = task.uuid if task else task_uuid

    share_token = db.exec(
        select(TranscriptShareToken)
        .where(TranscriptShareToken.token == token)
        .where(TranscriptShareToken.task_uuid == target_uuid)
    ).first()
    
    if not share_token:
        raise HTTPException(status_code=404, detail="Share token not found")

    share_token.revoked_at = datetime.utcnow()
    db.add(share_token)
    db.commit()
    return {"status": "success", "message": "Token revoked"}

@share_router.get("/transcripts/share/{token}", response_class=HTMLResponse)
def render_share_page(token: str, db: Session = Depends(get_db_session)):
    share_token = db.exec(
        select(TranscriptShareToken).where(TranscriptShareToken.token == token)
    ).first()

    if not share_token or not share_token.is_valid():
        return HTMLResponse(
            content="""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Link Unavailable - Whizzper</title>
  <meta name="robots" content="noindex, nofollow">
</head>
<body style="font-family: sans-serif; text-align: center; padding: 50px; background: #f8fafc;">
  <h2>This link is no longer available</h2>
  <p>The requested transcript share token is invalid, expired, or has been revoked.</p>
</body>
</html>""",
            status_code=404
        )

    task = find_task_by_id_or_uuid(db, share_token.task_uuid)
    if not task or not task.result:
        return HTMLResponse(
            content="""<!DOCTYPE html><html><head><meta name="robots" content="noindex, nofollow"></head><body><h2>Transcript unavailable</h2></body></html>""",
            status_code=404
        )

    segments = []
    if isinstance(task.result, dict):
        segments = task.result.get("segments", [])
    elif isinstance(task.result, list):
        segments = task.result

    total_count = len(segments)
    title = task.file_name or "Transcript"
    date_str = task.created_at.strftime("%b %d, %Y, %I:%M %p") if hasattr(task, 'created_at') and task.created_at else ""

    lines_html = []
    for idx, seg in enumerate(segments):
        start_val = seg.get("start", 0.0)
        end_val = seg.get("end", 0.0)
        text_val = (seg.get("text") or "").strip()
        lines_html.append(
            f'<div class="segment-block" data-idx="{idx}">'
            f'<div class="segment-meta">{idx + 1}<br>{start_val:.3f} --> {end_val:.3f}</div>'
            f'<div class="transcript-line" data-index="{idx}" data-start="{start_val}" data-end="{end_val}">{text_val}</div>'
            f'</div>'
        )

    lines_rendered = "\n".join(lines_html)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - Whizzper Translation Tool</title>
  <meta name="robots" content="noindex, nofollow">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #f1f5f9;
      background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
      background-size: 16px 16px;
      color: #1e293b;
      margin: 0;
      padding: 0 0 100px 0;
    }}
    .top-header {{
      background: #0284c7;
      color: white;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .top-header h2 {{ margin: 0; font-size: 1.1rem; font-weight: 700; }}
    .main-container {{
      max-width: 760px;
      margin: 30px auto;
      background: #ffffff;
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.05);
      border: 1px solid #e2e8f0;
    }}
    .doc-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .doc-title {{ margin: 0 0 6px 0; font-size: 1.5rem; font-weight: 800; color: #0f172a; }}
    .doc-date {{ font-size: 0.85rem; color: #64748b; }}
    .top-download-btn {{
      background: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
      padding: 8px 16px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .top-download-btn:hover {{ background: #e2e8f0; color: #0f172a; }}
    
    #transcript-container {{
      background: #fafafa;
      border: 1px solid #f1f5f9;
      border-radius: 8px;
      padding: 24px;
      line-height: 1.6;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9rem;
    }}
    .segment-block {{ margin-bottom: 20px; }}
    .segment-meta {{ color: #64748b; font-size: 0.8rem; margin-bottom: 4px; white-space: pre-line; }}
    .transcript-line {{ color: #0f172a; word-break: break-word; }}

    .sticky-bar {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: #ffffff;
      border-top: 1px solid #e2e8f0;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      z-index: 9999;
      box-shadow: 0 -4px 12px rgba(0,0,0,0.05);
    }}
    .mode-btn {{
      background: #f1f5f9;
      color: #475569;
      border: 1px solid #cbd5e1;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .mode-btn:hover {{ background: #e2e8f0; color: #0f172a; }}
    .mode-btn.active {{ background: #0284c7; color: #ffffff; border-color: #0284c7; }}
    .error-banner {{ background: #fef2f2; color: #991b1b; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; display: none; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class="top-header">
    <h2>Whizzper Translation Tool</h2>
  </div>

  <div class="main-container">
    <div class="doc-header">
      <div>
        <h1 class="doc-title">{title}</h1>
        <div class="doc-date">{date_str}</div>
      </div>
      <button id="main-download-btn" class="top-download-btn" onclick="triggerActiveDownload()">
        📥 Download SRT
      </button>
    </div>

    <div id="error-message" class="error-banner"></div>

    <div id="transcript-container" data-total="{total_count}">
{lines_rendered}
    </div>
  </div>

  <div class="sticky-bar">
    <button id="btn-mode-txt" class="mode-btn" onclick="switchMode('txt')">📄 Translate TXT</button>
    <button id="btn-mode-srt" class="mode-btn active" onclick="switchMode('srt')">🎬 Translate SRT</button>
    <button id="btn-mode-vtt" class="mode-btn" onclick="switchMode('vtt')">🎬 Translate VTT</button>
  </div>

  <script>
    let currentMode = 'srt';

    function pad(num, len = 2) {{
      return String(num).padStart(len, '0');
    }}

    function formatTime(seconds, isVtt) {{
      const hrs = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);
      const ms = Math.floor((seconds % 1) * 1000);
      const msSep = isVtt ? '.' : ',';
      return `${{pad(hrs)}}:${{pad(mins)}}:${{pad(secs)}}${{msSep}}${{pad(ms, 3)}}`;
    }}

    function switchMode(mode) {{
      currentMode = mode;
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById(`btn-mode-${{mode}}`);
      if (activeBtn) activeBtn.classList.add('active');

      const mainDlBtn = document.getElementById('main-download-btn');
      if (mainDlBtn) {{
        mainDlBtn.innerText = `📥 Download ${{mode.toUpperCase()}}`;
      }}

      const blocks = document.querySelectorAll('.segment-block');
      blocks.forEach((block) => {{
        const metaEl = block.querySelector('.segment-meta');
        const lineEl = block.querySelector('.transcript-line');
        if (!metaEl || !lineEl) return;

        const idx = parseInt(lineEl.getAttribute('data-index') || '0', 10);
        const start = parseFloat(lineEl.getAttribute('data-start') || '0');
        const end = parseFloat(lineEl.getAttribute('data-end') || '0');

        if (mode === 'txt') {{
          metaEl.style.display = 'none';
        }} else if (mode === 'srt') {{
          metaEl.style.display = 'block';
          metaEl.innerHTML = `${{idx + 1}}<br>${{formatTime(start, false)}} --> ${{formatTime(end, false)}}`;
        }} else if (mode === 'vtt') {{
          metaEl.style.display = 'block';
          metaEl.innerHTML = `${{idx + 1}}<br>${{formatTime(start, true)}} --> ${{formatTime(end, true)}}`;
        }}
      }});
    }}

    function extractDOMTranscript() {{
      const container = document.getElementById('transcript-container');
      if (!container) return {{ segments: [], error: "Transcript container missing" }};
      const expectedTotal = parseInt(container.getAttribute('data-total') || '0', 10);
      const lineElements = Array.from(container.querySelectorAll('.transcript-line'));
      
      const segments = [];
      for (const el of lineElements) {{
        const idx = parseInt(el.getAttribute('data-index') || '-1', 10);
        const start = parseFloat(el.getAttribute('data-start') || '0');
        const end = parseFloat(el.getAttribute('data-end') || '0');
        const text = el.innerText ? el.innerText.trim() : '';

        if (isNaN(idx) || isNaN(start) || isNaN(end) || !text) continue;
        segments.push({{ index: idx, start: start, end: end, text: text }});
      }}

      segments.sort((a, b) => a.index - b.index);

      if (segments.length !== expectedTotal) {{
        return {{ segments: segments, error: `Line count mismatch: expected ${{expectedTotal}} segments but extracted ${{segments.length}}` }};
      }}
      return {{ segments: segments }};
    }}

    function buildSRT(segments) {{
      return segments.map((s, i) => `${{i + 1}}\\n${{formatTime(s.start, false)}} --> ${{formatTime(s.end, false)}}\\n${{s.text}}\\n`).join('\\n');
    }}

    function buildVTT(segments) {{
      return 'WEBVTT\\n\\n' + segments.map((s, i) => `${{i + 1}}\\n${{formatTime(s.start, true)}} --> ${{formatTime(s.end, true)}}\\n${{s.text}}\\n`).join('\\n');
    }}

    function buildTXT(segments) {{
      return segments.map(s => s.text).join('\\n');
    }}

    function triggerActiveDownload() {{
      const errBox = document.getElementById('error-message');
      errBox.style.display = 'none';
      errBox.innerText = '';

      const res = extractDOMTranscript();
      if (res.error) {{
        errBox.innerText = res.error;
        errBox.style.display = 'block';
        return;
      }}

      let content = '', filename = `transcript.${{currentMode}}`, mime = 'text/plain';
      if (currentMode === 'srt') {{ content = buildSRT(res.segments); mime = 'application/x-subrip'; }}
      else if (currentMode === 'vtt') {{ content = buildVTT(res.segments); mime = 'text/vtt'; }}
      else if (currentMode === 'txt') {{ content = buildTXT(res.segments); }}

      const blob = new Blob([content], {{ type: mime }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=full_html)
