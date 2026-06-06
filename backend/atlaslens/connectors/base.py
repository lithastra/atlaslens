from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from atlaslens.models.event import Deployment, Product


@dataclass
class RawEvent:
    source_id: str
    occurred_at: datetime
    event_type: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        # Normalise every event time to UTC on the way in. Sources may return
        # timestamps in the instance's local timezone (e.g. Atlassian returns
        # audit times with a +09:00 offset for a JST-configured site); a naive
        # value is assumed to already be UTC.
        if self.occurred_at.tzinfo is None:
            self.occurred_at = self.occurred_at.replace(tzinfo=UTC)
        else:
            self.occurred_at = self.occurred_at.astimezone(UTC)


Cursor = str | None


@runtime_checkable
class Connector(Protocol):
    product: Product
    deployment: Deployment

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]: ...
    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]: ...
