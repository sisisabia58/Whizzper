from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index
from backend.db.db_instance import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, index=True, nullable=False, default="QUEUED")
    current_stage = Column(String, nullable=False, default="queued")
    progress_percent = Column(Integer, nullable=False, default=0)
    eta_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
