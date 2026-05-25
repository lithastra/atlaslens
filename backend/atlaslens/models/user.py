from datetime import UTC, datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    id: str = Field(alias="_id", default="")
    username: str
    password_hash: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    disabled: bool = False

    model_config = {"populate_by_name": True}
