from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from backend.db.db_instance import get_db_session
from backend.db.task.dao import (
    get_task_status_from_db,
    get_all_tasks_status_from_db,
    delete_task_from_db,
)
from backend.db.task.models import (
    TasksResult,
    Task,
    TaskStatusResponse,
    TaskType
)
from backend.common.models import (
    Response,
)
from backend.common.compresser import compress_files, find_file_by_hash
from modules.utils.paths import BACKEND_CACHE_DIR

task_router = APIRouter(prefix="/task", tags=["Tasks"])


from fastapi import Response as FastAPIResponse

@task_router.get(
    "/all",
    response_model=TasksResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve All Task Statuses",
    description="Retrieve the statuses of all tasks available in the system.",
)
async def get_all_tasks_status(
    response: FastAPIResponse,
    session: Session = Depends(get_db_session),
) -> TasksResult:
    """
    Retrieve all tasks.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return get_all_tasks_status_from_db(session=session)


@task_router.get(
    "/{identifier}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Task by Identifier",
    description="Retrieve the specific task by its identifier.",
)
async def get_task(
    identifier: str,
    session: Session = Depends(get_db_session),
) -> TaskStatusResponse:
    """
    Retrieve the specific task by its identifier.
    """
    task = get_task_status_from_db(identifier=identifier, session=session)

    if task is not None:
        return task.to_response()
    else:
        raise HTTPException(status_code=404, detail="Identifier not found")


@task_router.get(
    "/file/{identifier}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve FileResponse Task by Identifier",
    description="Retrieve the file response task by its identifier. You can use this endpoint if you need to download"
                " The file as a response",
)
async def get_file_task(
    identifier: str,
    session: Session = Depends(get_db_session),
) -> FileResponse:
    """
    Retrieve the downloadable file response of a specific task by its identifier.
    Compressed by ZIP basically.
    """
    task = get_task_status_from_db(identifier=identifier, session=session)

    if task is not None:
        if task.task_type == TaskType.BGM_SEPARATION:
            output_zip_path = os.path.join(BACKEND_CACHE_DIR, f"{identifier}_bgm_separation.zip")
            instrumental_path = find_file_by_hash(
                os.path.join(BACKEND_CACHE_DIR, "UVR", "instrumental"),
                task.result["instrumental_hash"]
            )
            vocal_path = find_file_by_hash(
                os.path.join(BACKEND_CACHE_DIR, "UVR", "vocals"),
                task.result["vocal_hash"]
            )

            output_zip_path = compress_files(
                [instrumental_path, vocal_path],
                output_zip_path
            )
            return FileResponse(
                path=output_zip_path,
                status_code=200,
                filename=output_zip_path,
                media_type="application/zip"
            )
        else:
            raise HTTPException(status_code=404, detail=f"File download is only supported for bgm separation."
                                                        f" The given type is {task.task_type}")
    else:
        raise HTTPException(status_code=404, detail="Identifier not found")


# Delete method, commented by default because this endpoint is likely to require special permissions
# @task_router.delete(
#     "/{identifier}",
#     response_model=Response,
#     status_code=status.HTTP_200_OK,
#     summary="Delete Task by Identifier",
#     description="Delete a task from the system using its identifier.",
# )
async def delete_task(
    identifier: str,
    session: Session = Depends(get_db_session),
) -> Response:
    """
    Delete a task by its identifier.
    """
    if delete_task_from_db(identifier, session):
        return Response(identifier=identifier, message="Task deleted")
    else:
        raise HTTPException(status_code=404, detail="Task not found")


@task_router.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    session: Session = Depends(get_db_session)
):
    from backend.db.batch.dao import get_batch_from_db
    batch = get_batch_from_db(batch_id, session)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found")
        
    children = session.query(Task).filter(Task.batch_id == batch_id).all()
    
    # Calculate progress aggregate
    tot = len(children)
    progress_sum = sum(c.progress or 0.0 for c in children)
    aggregate_progress = progress_sum / tot if tot > 0 else 0.0
    
    return {
        "batch_id": batch.batch_id,
        "folder_name": batch.folder_name,
        "source_type": batch.source_type,
        "status": batch.status,
        "total_files": batch.total_files,
        "completed_files": batch.completed_files,
        "failed_files": batch.failed_files,
        "progress": round(aggregate_progress, 2),
        "children": [
            {
                "identifier": c.uuid,
                "name": c.file_name,
                "path": c.source_path,
                "status": c.status,
                "progress": c.progress,
                "duration": c.duration,
                "error": c.error
            } for c in children
        ]
    }


@task_router.get("/batch/{batch_id}/download")
async def download_batch_zip(
    batch_id: str,
    session: Session = Depends(get_db_session)
):
    import io
    from backend.db.batch.dao import get_batch_from_db
    from backend.common.zip_writer import build_srt_zip
    from fastapi.responses import StreamingResponse

    batch = get_batch_from_db(batch_id, session)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found")
        
    children = session.query(Task).filter(Task.batch_id == batch_id).all()
    completed = [c for c in children if c.status == "completed"]
    if not completed:
        raise HTTPException(status_code=409, detail="No completed files yet")
        
    zip_bytes = build_srt_zip(completed)
    
    headers = {}
    incomplete_count = len(children) - len(completed)
    if incomplete_count > 0:
        headers["X-Whizzper-Incomplete"] = str(incomplete_count)
        
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={batch.folder_name}_subtitles.zip",
            **headers
        }
    )


