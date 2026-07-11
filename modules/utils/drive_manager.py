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
            
        q = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        else:
            q += " and 'root' in parents"
            
        results = self.service.files().list(
            q=q,
            pageSize=50,
            fields="nextPageToken, files(id, name, modifiedTime, owners)",
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        return results

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
            
            # Extract to 64k mono MP3, then read it into the target WAV layout
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                mp3_path = mp3_file.name
                
            cmd = ["ffmpeg", "-y", "-i", raw_path, "-vn", "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", mp3_path]
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
