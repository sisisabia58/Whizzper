import os
import subprocess
import yt_dlp

# Write cookies.txt from environment variable YOUTUBE_COOKIES if available
if os.environ.get("YOUTUBE_COOKIES"):
    try:
        raw_cookies = os.environ["YOUTUBE_COOKIES"]
        fixed_lines = []
        for line in raw_cookies.splitlines():
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                fixed_lines.append(line)
                continue
            parts = line_stripped.split()
            if len(parts) >= 7:
                # Reconstruct tab-separated Netscape format
                reconstructed = "\t".join(parts[:6] + [" ".join(parts[6:])])
                fixed_lines.append(reconstructed)
            else:
                fixed_lines.append(line)
        
        content = "\n".join(fixed_lines)
        if not content.startswith("# Netscape HTTP Cookie File"):
            content = "# Netscape HTTP Cookie File\n" + content
            
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"Error writing YOUTUBE_COOKIES environment variable to cookies.txt: {e}")

class YoutubeData:
    def __init__(self, title, thumbnail_url, description, url):
        self.title = title
        self.thumbnail_url = thumbnail_url
        self.description = description
        self.url = url

def get_ytdata(link: str) -> YoutubeData:
    ydl_opts = {
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
    }
    cookie_paths = ["cookies.txt", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cookies.txt")]
    for path in cookie_paths:
        if os.path.exists(path):
            ydl_opts['cookiefile'] = path
            break
            
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(link, download=False)
        title = info.get('title', 'Unknown Title')
        thumbnail = info.get('thumbnail', '')
        description = info.get('description', '')
        return YoutubeData(title, thumbnail, description, link)

def get_ytmetas(link: str):
    try:
        yt = get_ytdata(link)
        return yt.thumbnail_url, yt.title, yt.description
    except Exception as e:
        print(f"Error fetching YouTube metadata: {e}")
        return None, f"Error: {e}", ""

def get_ytaudio(ytdata: YoutubeData) -> str:
    audio_path = os.path.join("modules", "yt_tmp.wav")
    temp_audio_path = os.path.join("modules", "yt_tmp_fixed.wav")
    
    if os.path.exists(audio_path):
        try:
            os.remove(audio_path)
        except OSError:
            pass
            
    if os.path.exists(temp_audio_path):
        try:
            os.remove(temp_audio_path)
        except OSError:
            pass
            
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join("modules", "yt_tmp_downloaded.%(ext)s"),
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
    }
    cookie_paths = ["cookies.txt", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cookies.txt")]
    for path in cookie_paths:
        if os.path.exists(path):
            ydl_opts['cookiefile'] = path
            break
            
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(ytdata.url, download=True)
        downloaded_filename = ydl.prepare_filename(info)
        
    try:
        # Convert to valid wav audio file using ffmpeg.
        # Fix for : https://github.com/jhj0517/Whisper-WebUI/issues/304
        subprocess.run([
            'ffmpeg', '-y',
            '-i', downloaded_filename,
            temp_audio_path
        ], check=True)

        os.replace(temp_audio_path, audio_path)
        
        # Clean up downloaded raw audio if it's different from final audio_path
        if os.path.exists(downloaded_filename) and downloaded_filename != audio_path:
            try:
                os.remove(downloaded_filename)
            except OSError:
                pass
                
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg conversion: {e}")
        return None
