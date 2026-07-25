from typing import Optional
from datetime import datetime
from uuid import uuid4
from sqlmodel import SQLModel, Field, Column, String

def generate_share_token() -> str:
    return f"st_{uuid4().hex[:16]}"

class TranscriptShareToken(SQLModel, table=True):
    __tablename__ = "transcript_share_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(default_factory=generate_share_token, sa_column=Column(String, unique=True, index=True))
    task_uuid: str = Field(index=True, description="UUID of associated transcript task")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    revoked_at: Optional[datetime] = Field(default=None, description="Revocation timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    def is_valid(self, at_time: Optional[datetime] = None) -> bool:
        check_time = at_time or datetime.utcnow()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and check_time > self.expires_at:
            return False
        return True
