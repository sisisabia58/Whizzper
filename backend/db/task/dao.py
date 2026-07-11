from typing import Dict, Any
import math
from sqlalchemy.orm import Session
from fastapi import Depends

from ..db_instance import handle_database_errors, get_db_session
from .models import Task, TasksResult, TaskStatus


def clean_json_val(val: Any) -> Any:
    """Recursively clean floats (inf, -inf, nan) to make them JSON-serializable for SQL databases."""
    if isinstance(val, dict):
        return {k: clean_json_val(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [clean_json_val(v) for v in val]
    elif isinstance(val, float):
        if math.isinf(val) or math.isnan(val):
            return None
        return val
    return val


@handle_database_errors
def add_task_to_db(
    session,
    status=TaskStatus.QUEUED,
    task_type=None,
    language=None,
    task_params=None,
    file_name=None,
    url=None,
    audio_duration=None,
    batch_id=None,
    source_file_id=None,
    source_path=None,
    source_parent_id=None,
):
    """
    Add task to the db
    """
    if task_params is not None:
        task_params = clean_json_val(task_params)

    task = Task(
        status=status,
        language=language,
        file_name=file_name,
        url=url,
        task_type=task_type,
        task_params=task_params,
        audio_duration=audio_duration,
        batch_id=batch_id,
        source_file_id=source_file_id,
        source_path=source_path,
        source_parent_id=source_parent_id,
    )
    session.add(task)
    session.commit()
    return task.uuid


@handle_database_errors
def update_task_status_in_db(
    identifier: str,
    update_data: Dict[str, Any],
    session: Session,
):
    """
    Update task status and attributes in the database.

    Args:
        identifier (str): Identifier of the task to be updated.
        update_data (Dict[str, Any]): Dictionary containing the attributes to update along with their new values.
        session (Session, optional): Database session. Defaults to Depends(get_db_session).

    Returns:
        None
    """
    task = session.query(Task).filter_by(uuid=identifier).first()
    if task:
        for key, value in update_data.items():
            if key == "task_params" and value is not None:
                value = clean_json_val(value)
            elif key == "result" and value is not None:
                value = clean_json_val(value)
            setattr(task, key, value)
        session.commit()


@handle_database_errors
def get_task_status_from_db(
    identifier: str, session: Session
):
    """Retrieve task status from db"""
    task = session.query(Task).filter(Task.uuid == identifier).first()
    if task:
        return task
    else:
        return None


@handle_database_errors
def get_all_tasks_status_from_db(session: Session):
    """Get all tasks from db"""
    from sqlalchemy.orm import defer
    tasks = session.query(Task).options(defer(Task.result)).order_by(Task.created_at.desc()).all()
    return TasksResult(tasks=tasks)


@handle_database_errors
def delete_task_from_db(identifier: str, session: Session):
    """Delete task from db"""
    task = session.query(Task).filter(Task.uuid == identifier).first()

    if task:
        # If the task exists, delete it from the database
        session.delete(task)
        session.commit()
        return True
    else:
        # If the task does not exist, return False
        return False
