from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CanonicalGroup(BaseModel):
    id: str = Field(alias="_id")
    name: str
    description: str = ""
    source: str = "atlassian-org"
    active: bool = True

    model_config = {"populate_by_name": True}


class SourceGroup(BaseModel):
    id: str = Field(alias="_id")
    namespace: str
    native_id: str
    native_name: str
    scope: str = ""
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    model_config = {"populate_by_name": True}


class GroupMap(BaseModel):
    id: str = Field(alias="_id")
    source_group_id: str
    canonical_group_id: str
    match_method: str = "auto_name"
    confidence: float = 1.0
    mapped_by: str = "system"
    mapped_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    model_config = {"populate_by_name": True}
