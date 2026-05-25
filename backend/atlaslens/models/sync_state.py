from datetime import datetime

from pydantic import BaseModel, Field


class SyncState(BaseModel):
    id: str = Field(alias="_id")
    cursor: str = ""
    last_success_at: datetime | None = None
    last_error: str | None = None

    model_config = {"populate_by_name": True}
