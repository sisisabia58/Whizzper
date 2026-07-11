from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlmodel import SQLModel, Field

class DriveConnection(SQLModel, table=True):
    __tablename__ = "drive_connections"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(default_factory=lambda: str(uuid4()), unique=True)
    owner_key: str = Field(index=True)
    provider: str = Field(default="google")
    account_email: str
    account_sub: str
    access_token_enc: bytes
    refresh_token_enc: bytes
    token_expiry: datetime
    scopes: str
    status: str = Field(default="ACTIVE")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
