import pytest
from backend.db.models import Task

def test_extended_task_columns_exist():
    task = Task(
        identifier="task-123",
        status="QUEUED",
        current_stage="queued",
        progress_percent=0,
        eta_seconds=120
    )
    assert task.identifier == "task-123"
    assert task.current_stage == "queued"
    assert task.progress_percent == 0
    assert task.eta_seconds == 120
