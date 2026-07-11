from sqlmodel import SQLModel, Field, JSON, Column
from datetime import datetime
from typing import Optional

class BatchJob(SQLModel, table=True):
    __tablename__ = "batch_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(unique=True, index=True)
    source_type: str = Field(default="drive_folder")
    source_url: Optional[str] = Field(default=None)
    folder_name: str = Field(index=True)
    status: str = Field(default="queued") # queued, in_progress, completed, partial_failed, failed
    total_files: int = Field(default=0)
    completed_files: int = Field(default=0)
    failed_files: int = Field(default=0)
    task_params: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = Field(default=None)
    access_mode: str = Field(default="link")
    connection_id: Optional[str] = Field(default=None)
    writeback_enabled: bool = Field(default=False)
    uploaded_files: int = Field(default=0)
    writeback_failed_files: int = Field(default=0)
