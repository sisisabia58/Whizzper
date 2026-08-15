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
