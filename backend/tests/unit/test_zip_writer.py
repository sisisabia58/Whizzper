import zipfile
import io
from backend.common.zip_writer import compile_srt, build_srt_zip
from backend.db.task.models import Task

def test_compile_srt_structure():
    segments = [{"start": 1.5, "end": 4.2, "text": "Hello World"}]
    srt = compile_srt(segments)
    assert "1\n00:00:01,500 --> 00:00:04,200\nHello World" in srt

def test_build_srt_zip():
    task1 = Task(status="completed", file_name="first_file.mp3", source_path="day1/first_file.mp3", result=[{"start": 0.0, "end": 2.0, "text": "Test one"}])
    task2 = Task(status="completed", file_name="second_file.wav", source_path="day2/second_file.wav", result=[{"start": 1.0, "end": 3.0, "text": "Test two"}])
    
    zip_data = build_srt_zip([task1, task2])
    
    # Read zip content
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        namelist = zf.namelist()
        assert "day1/first_file.srt" in namelist
        assert "day2/second_file.srt" in namelist
        
        content1 = zf.read("day1/first_file.srt").decode("utf-8")
        assert "Test one" in content1
