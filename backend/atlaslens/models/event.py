from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ObjectRef(BaseModel):
    id: str
    name: str
    container: str | None = None


Product = Literal["jira", "confluence", "bitbucket", "jsm"]
Deployment = Literal["cloud", "datacenter"]
Pipeline = Literal["audit", "activity"]
Category = Literal["security", "content"]
Severity = Literal["low", "medium", "high"]
ObjectType = Literal[
    "ticket",
    "page",
    "repo",
    "commit",
    "pull_request",
    "request",
    "user",
    "group",
    "project",
    "space",
    "config",
]


class Event(BaseModel):
    id: str = Field(alias="_id")
    occurred_at: datetime
    product: Product
    deployment: Deployment
    pipeline: Pipeline
    actor_id: str | None = None
    actor_raw: str
    operation: str
    category: Category
    severity: Severity
    object_type: ObjectType
    object_ref: ObjectRef
    context: dict[str, Any] = Field(default_factory=dict)
    source_ip: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    model_config = {"populate_by_name": True}

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)
