from pathlib import Path

SCRIPT = Path("scripts/start_workers.sh").read_text()


def test_default_profile_is_idle():
    assert 'PROFILE="${WORKER_PROFILE:-idle}"' in SCRIPT


def test_idle_profile_enables_beat():
    idle_block = SCRIPT.split("idle)", 1)[1].split("batch)", 1)[0]
    assert 'CELERY_ENABLE_BEAT:=1' in idle_block
    assert 'CELERY_ENABLE_BEAT:=0' not in idle_block


def test_batch_profile_enables_beat():
    batch_block = SCRIPT.split("batch)", 1)[1].split("*)", 1)[0]
    assert 'CELERY_ENABLE_BEAT:=1' in batch_block


def test_transcribe_worker_uses_threads_pool():
    assert "-P threads" in SCRIPT
    assert "-Q transcribe" in SCRIPT


def test_download_worker_does_not_use_threads_pool():
    download_line = [ln for ln in SCRIPT.splitlines() if "-Q download " in ln][0]
    assert "-P threads" not in download_line
