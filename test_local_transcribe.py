import os
import sys
import time

# Set endpoint URL for Modal GPU backend
os.environ["MODAL_WEB_ENDPOINT_URL"] = "https://revigefarta--whizzper-backend-transcribe-endpoint.modal.run"

from modules.whisper.whisper_factory import WhisperFactory

video_path = r"C:\Users\wisnu\Downloads\Intro to Replit： Idea to App in 5 minutes 720p30fps 343.mp4"
output_dir = r"d:\Tranzscribe\Whisper-WebUI\outputs"

print(f"Testing transcription on: {video_path}")
print("Connecting to Modal GPU endpoint...")

try:
    pipeline = WhisperFactory.create_whisper_inference("modal", output_dir=output_dir)
    result_str, result_file_paths = pipeline.transcribe_file(
        files=[video_path],
        file_format="SRT",
        add_timestamp=False
    )
    print("\nSUCCESS!")
    print(f"Result file paths: {result_file_paths}")
    print("\n--- SUBTITLE PREVIEW ---")
    print(result_str[:1000])
except Exception as e:
    import traceback
    print(f"\nERROR DURING TRANSCRIPTION: {e}")
    traceback.print_exc()
