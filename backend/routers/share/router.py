from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from backend.db.db_instance import get_db_session
from backend.db.task.models import Task
from backend.db.share.models import TranscriptShareToken, generate_share_token

share_router = APIRouter(tags=["Transcript Share"])

@share_router.post("/api/transcripts/{task_uuid}/share")
def create_share_token(
    task_uuid: str,
    expires_in_hours: Optional[int] = 72,
    db: Session = Depends(get_db_session)
):
    task = db.exec(select(Task).where(Task.uuid == task_uuid)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Transcript task not found")
    
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None
    
    # Reuse existing active token if present
    existing = db.exec(
        select(TranscriptShareToken)
        .where(TranscriptShareToken.task_uuid == task_uuid)
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
        task_uuid=task_uuid,
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
    share_token = db.exec(
        select(TranscriptShareToken)
        .where(TranscriptShareToken.token == token)
        .where(TranscriptShareToken.task_uuid == task_uuid)
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
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
  <h2>This link is no longer available</h2>
  <p>The requested transcript share token is invalid, expired, or has been revoked.</p>
</body>
</html>""",
            status_code=404
        )

    task = db.exec(select(Task).where(Task.uuid == share_token.task_uuid)).first()
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

    lines_html = []
    for idx, seg in enumerate(segments):
        start_val = seg.get("start", 0.0)
        end_val = seg.get("end", 0.0)
        text_val = (seg.get("text") or "").strip()
        lines_html.append(
            f'<div class="transcript-line" data-index="{idx}" data-start="{start_val}" data-end="{end_val}">{text_val}</div>'
        )

    lines_rendered = "\n".join(lines_html)
    total_count = len(segments)
    title = task.file_name or "Transcript"

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - Whizzper Shared Transcript</title>
  <meta name="robots" content="noindex, nofollow">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px 20px 100px 20px; }}
    .header {{ max-width: 800px; margin: 0 auto 24px auto; background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; }}
    .header h1 {{ margin: 0 0 8px 0; font-size: 1.25rem; color: #38bdf8; }}
    #transcript-container {{ max-width: 800px; margin: 0 auto; background: #1e293b; padding: 24px; border-radius: 8px; border: 1px solid #334155; line-height: 1.6; }}
    .transcript-line {{ margin-bottom: 12px; padding: 8px 12px; background: #0f172a; border-radius: 4px; border-left: 3px solid #38bdf8; }}
    .sticky-bar {{ position: fixed; bottom: 0; left: 0; right: 0; background: #0f172a; border-top: 1px solid #334155; padding: 12px 24px; display: flex; align-items: center; justify-content: space-between; z-index: 9999; }}
    .btn {{ background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; margin-left: 8px; text-decoration: none; display: inline-block; }}
    .btn:hover {{ background: #0369a1; }}
    .hint {{ font-size: 0.85rem; color: #94a3b8; }}
    .error-banner {{ background: #7f1d1d; color: #fca5a5; padding: 8px 12px; border-radius: 4px; font-size: 0.9rem; display: none; margin-right: 12px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{title}</h1>
    <div class="hint">Translation may still be loading — refresh if text looks incomplete.</div>
  </div>

  <div id="transcript-container" data-total="{total_count}">
{lines_rendered}
  </div>

  <div class="sticky-bar">
    <div id="error-message" class="error-banner"></div>
    <div>
      <button class="btn" onclick="exportDOM('srt')">Download SRT</button>
      <button class="btn" onclick="exportDOM('vtt')">Download VTT</button>
      <button class="btn" onclick="exportDOM('txt')">Download TXT</button>
    </div>
  </div>

  <script>
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

    function formatTime(seconds, isVtt) {{
      const pad = (num, len = 2) => String(num).padStart(len, '0');
      const hrs = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);
      const ms = Math.floor((seconds % 1) * 1000);
      const msSep = isVtt ? '.' : ',';
      return `${{pad(hrs)}}:${{pad(mins)}}:${{pad(secs)}}${{msSep}}${{pad(ms, 3)}}`;
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

    function exportDOM(format) {{
      const errBox = document.getElementById('error-message');
      errBox.style.display = 'none';
      errBox.innerText = '';

      const res = extractDOMTranscript();
      if (res.error) {{
        errBox.innerText = res.error;
        errBox.style.display = 'block';
        return;
      }}

      let content = '', filename = `transcript.${{format}}`, mime = 'text/plain';
      if (format === 'srt') {{ content = buildSRT(res.segments); mime = 'application/x-subrip'; }}
      else if (format === 'vtt') {{ content = buildVTT(res.segments); mime = 'text/vtt'; }}
      else if (format === 'txt') {{ content = buildTXT(res.segments); }}

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
