from modules.utils.drive_manager import parse_folder_id

def test_parse_folder_id():
    url = "https://drive.google.com/drive/folders/1A2B3C-4D5E6F_7G8H9I?usp=sharing"
    assert parse_folder_id(url) == "1A2B3C-4D5E6F_7G8H9I"

    url2 = "https://drive.google.com/open?id=1A2B3C-4D5E6F_7G8H9I"
    # Open URL isn't a direct folders/ ID, but let's test a non-folders URL returns None
    assert parse_folder_id(url2) is None


def test_download_and_extract_audio(monkeypatch):
    from unittest.mock import MagicMock
    import os
    
    # Mock Drive service build and MediaIoBaseDownload
    mock_service = MagicMock()
    mock_request = MagicMock()
    mock_service.files().get_media.return_value = mock_request
    
    # Mock MediaIoBaseDownload constructor and next_chunk
    mock_downloader = MagicMock()
    mock_downloader.next_chunk.return_value = (None, True)
    
    mock_media_io_constructor = MagicMock(return_value=mock_downloader)
    
    # Import target modules for monkeypatching
    import googleapiclient.discovery
    import googleapiclient.http
    import subprocess
    
    monkeypatch.setenv("GOOGLE_DRIVE_API_KEY", "fake_key")
    
    import modules.utils.drive_manager
    monkeypatch.setattr(modules.utils.drive_manager, "build", lambda *a, **k: mock_service)
    
    import googleapiclient.http
    monkeypatch.setattr(googleapiclient.http, "MediaIoBaseDownload", mock_media_io_constructor)
    
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MagicMock(returncode=0))
    
    from modules.utils.drive_manager import DriveManager
    dm = DriveManager()
    
    # Run download
    dm.download_and_extract_audio("file_id_123", "dummy_output.wav")
    
    # Assert get_media was called with correct parameters
    mock_service.files().get_media.assert_called_once_with(fileId="file_id_123")
    mock_downloader.next_chunk.assert_called_once()

