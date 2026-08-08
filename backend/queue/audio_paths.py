import os

from modules.utils.paths import BACKEND_CACHE_DIR


def wav_path_for_task(task_uuid: str) -> str:
    return os.path.join(BACKEND_CACHE_DIR, f"{task_uuid}.wav")


def wav_exists(task_uuid: str) -> bool:
    return os.path.exists(wav_path_for_task(task_uuid))
