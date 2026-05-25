from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from atlaslens.models.event import Deployment, Product


@dataclass
class RawEvent:
    source_id: str
    occurred_at: datetime
    event_type: str
    payload: dict[str, Any]


Cursor = str | None


@runtime_checkable
class Connector(Protocol):
    product: Product
    deployment: Deployment

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]: ...
    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]: ...
