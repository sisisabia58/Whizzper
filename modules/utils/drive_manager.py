import os
import re
import urllib.parse
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build

MEDIA_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.mp4', '.mov', '.mkv', '.flac', '.aac'}

def parse_folder_id(url: str) -> Optional[str]:
    match = re.search(r'folders/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

class DriveManager:
    def __init__(self, credentials_dict: Optional[dict] = None):
        self.api_key = os.environ.get("GOOGLE_DRIVE_API_KEY")
        if credentials_dict:
            from google.oauth2.credentials import Credentials
            creds = Credentials(**credentials_dict)
            self.service = build('drive', 'v3', credentials=creds)
        else:
            self.service = build('drive', 'v3', developerKey=self.api_key) if self.api_key else None

    def list_folders(self, parent_id: Optional[str] = None, page_token: Optional[str] = None) -> dict:
        if not self.service:
            raise ValueError("Google Drive service is not initialized")
            
        # 1. Fetch folders with auto-pagination
        q = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id and parent_id != 'root':
            q += f" and '{parent_id}' in parents"
        else:
            q += " and 'root' in parents"
            
        folders_list = []
        current_page_token = None
        while True:
            results = self.service.files().list(
                q=q,
                pageSize=1000,
                fields="nextPageToken, files(id, name, modifiedTime)",
                pageToken=current_page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            folders_list.extend(results.get('files', []))
            current_page_token = results.get('nextPageToken')
            if not current_page_token:
                break
                
        # 2. Fetch Shared Drives if at the root level
        if not parent_id or parent_id == 'root':
            try:
                drives_results = self.service.drives().list(pageSize=100).execute()
                for d in drives_results.get('drives', []):
                    folders_list.append({
                        "id": d.get("id"),
                        "name": f"📁 Shared Drive: {d.get('name')}"
                    })
            except Exception as e:
                # Fallback if scope does not support drives.list API
                pass

        # 3. Fetch media files inside the parent folder
        files_list = []
        if parent_id and parent_id != 'root':
            q_files = f"'{parent_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'"
            current_page_token = None
            while True:
                results = self.service.files().list(
                    q=q_files,
                    pageSize=1000,
                    fields="nextPageToken, files(id, name, mimeType, size, videoMediaMetadata)",
                    pageToken=current_page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True
                ).execute()
                for file in results.get('files', []):
                    name = file.get('name', '')
                    ext = os.path.splitext(name)[1].lower()
                    if ext in MEDIA_EXTENSIONS:
                        size_bytes = int(file.get('size', 0)) if file.get('size') else 0
                        size_mb = f"{size_bytes / (1024 * 1024):.1f} MB" if size_bytes > 0 else "0 MB"
                        metadata = file.get('videoMediaMetadata', {})
                        duration_min = round(float(metadata.get('durationMillis', 0)) / 60000.0, 1) if metadata else 0
                        files_list.append({
                            "id": file.get('id'),
                            "name": name,
                            "mime_type": file.get('mimeType'),
                            "size": size_mb,
                            "durationMin": duration_min if duration_min > 0 else None
                        })
                current_page_token = results.get('nextPageToken')
                if not current_page_token:
                    break
                    
        return {"folders": folders_list, "files": files_list}

    def scan_folder(self, folder_id: str, current_path: str = "") -> List[Dict[str, Any]]:
        if not self.service:
            raise ValueError("Google Drive service is not initialized")
        
        files_list = []
        page_token = None
        
        while True:
            q = f"'{folder_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=q,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, size, videoMediaMetadata)",
                pageToken=page_token
            ).execute()
            
            for file in results.get('files', []):
                name = file.get('name', '')
                file_id = file.get('id', '')
                mime_type = file.get('mimeType', '')
                
                if mime_type == 'application/vnd.google-apps.folder':
                    subfolder_path = f"{current_path}/{name}" if current_path else name
                    files_list.extend(self.scan_folder(file_id, subfolder_path))
                else:
                    ext = os.path.splitext(name)[1].lower()
                    is_media = ext in MEDIA_EXTENSIONS
                    size = int(file.get('size', 0)) if file.get('size') else 0
                    metadata = file.get('videoMediaMetadata', {})
                    duration = float(metadata.get('durationMillis', 0)) / 1000.0 if metadata else None
                    
                    files_list.append({
                        "file_id": file_id,
                        "name": name,
                        "path": f"{current_path}/{name}" if current_path else name,
                        "mime_type": mime_type,
                        "size_bytes": size,
                        "is_media": is_media,
                        "duration_sec": duration,
                        "skipped_reason": "unsupported_type" if not is_media else None,
                        "parent_id": folder_id
                    })
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return files_list

    def download_and_extract_audio(self, file_id: str, output_wav_path: str):
        if not self.service:
            raise ValueError("GOOGLE_DRIVE_API_KEY is not set")
            
        from googleapiclient.http import MediaIoBaseDownload
        
        request = self.service.files().get_media(fileId=file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as raw_file:
            raw_path = raw_file.name
            
        try:
            with open(raw_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            # Extract to 32k mono MP3, then read it into the target WAV layout
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                mp3_path = mp3_file.name
                
            cmd = ["ffmpeg", "-y", "-i", raw_path, "-vn", "-c:a", "libmp3lame", "-b:a", "32k", "-ac", "1", mp3_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Decode to final WAV for the pipeline
            cmd_wav = ["ffmpeg", "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", output_wav_path]
            subprocess.run(cmd_wav, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            os.remove(mp3_path)
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

    def upload_srt(self, filename: str, srt_content: str, parent_id: str, on_conflict: str = "version") -> str:
        from googleapiclient.http import MediaIoBaseUpload
        import io
        
        # Conflict checking
        if on_conflict == "skip" or on_conflict == "version":
            q = f"name = '{filename}' and '{parent_id}' in parents and trashed = false"
            results = self.service.files().list(q=q, fields="files(id)").execute()
            files = results.get("files", [])
            if files:
                if on_conflict == "skip":
                    return "" # Skip upload
                # For version, we uniquely suffix the filename
                base, ext = os.path.splitext(filename)
                filename = f"{base}_v2{ext}"

        file_metadata = {
            'name': filename,
            'parents': [parent_id]
        }
        media = MediaIoBaseUpload(
            io.BytesIO(srt_content.encode("utf-8")),
            mimetype='text/plain',
            resumable=True
        )
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        return file.get('id', '')
