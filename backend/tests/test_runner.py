from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from atlaslens.connectors.base import RawEvent
from atlaslens.ingest.runner import run_connector
from tests.mock_db import MockDB


def _make_raw_events(n: int) -> list[RawEvent]:
    return [
        RawEvent(
            source_id=str(i),
            occurred_at=datetime(2026, 3, 15, 10, i, tzinfo=UTC),
            event_type="User added to group",
            payload={
                "id": i,
                "summary": "User added to group",
                "remoteAddress": "192.168.1.1",
                "authorAccountId": "actor-1",
                "created": f"2026-03-15T10:{i:02d}:00.000+0000",
                "category": "group management",
                "eventSource": "Jira",
                "objectItem": {
                    "id": "obj-1",
                    "name": "admins",
                    "typeName": "GROUP",
                },
                "changedValues": [],
                "associatedItems": [],
            },
        )
        for i in range(n)
    ]


def _make_connector(raw_events: list[RawEvent]) -> Any:
    connector = AsyncMock()
    connector.product = "jira"
    connector.deployment = "cloud"
    connector.fetch_audit = AsyncMock(return_value=raw_events)
    connector.fetch_activity = AsyncMock(return_value=[])
    return connector


class TestRunner:
    @pytest.mark.asyncio
    async def test_basic_ingest(self) -> None:
        db = MockDB()
        connector = _make_connector(_make_raw_events(5))
        count = await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        assert count == 5
        assert len(db["events"].docs) == 5

    @pytest.mark.asyncio
    async def test_idempotent_upserts(self) -> None:
        db = MockDB()
        raw = _make_raw_events(3)
        connector = _make_connector(raw)

        count1 = await run_connector(db, connector, "audit")  # type: ignore[arg-type]
        count2 = await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        assert count1 == 3
        assert count2 == 3
        assert len(db["events"].docs) == 3

    @pytest.mark.asyncio
    async def test_cursor_advanced_on_success(self) -> None:
        db = MockDB()
        connector = _make_connector(_make_raw_events(2))
        await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        state = db["sync_state"].docs.get("cloud:jira:audit")
        assert state is not None
        assert state["cursor"] != ""
        assert state["last_error"] is None

    @pytest.mark.asyncio
    async def test_cursor_not_advanced_on_failure(self) -> None:
        db = MockDB()
        connector = AsyncMock()
        connector.product = "jira"
        connector.deployment = "cloud"
        connector.fetch_audit = AsyncMock(side_effect=RuntimeError("API down"))

        with pytest.raises(RuntimeError, match="API down"):
            await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        state = db["sync_state"].docs.get("cloud:jira:audit")
        assert state is not None
        assert state["last_error"] == "API down"
        assert "cursor" not in state

    @pytest.mark.asyncio
    async def test_empty_fetch(self) -> None:
        db = MockDB()
        connector = _make_connector([])
        count = await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        assert count == 0
        assert len(db["events"].docs) == 0

    @pytest.mark.asyncio
    async def test_natural_id_prevents_duplicates(self) -> None:
        db = MockDB()
        raw = _make_raw_events(3)
        connector1 = _make_connector(raw)
        connector2 = _make_connector(raw)

        await run_connector(db, connector1, "audit")  # type: ignore[arg-type]
        await run_connector(db, connector2, "audit")  # type: ignore[arg-type]

        assert len(db["events"].docs) == 3
        for doc_id in db["events"].docs:
            assert doc_id.startswith("cloud:jira:")

    @pytest.mark.asyncio
    async def test_cursor_loaded_from_state(self) -> None:
        db = MockDB()
        db["sync_state"].docs["cloud:jira:audit"] = {
            "_id": "cloud:jira:audit",
            "cursor": "2026-03-01T00:00:00+00:00",
            "last_success_at": None,
            "last_error": None,
        }
        connector = _make_connector([])
        await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        connector.fetch_audit.assert_called_once_with("2026-03-01T00:00:00+00:00")

    @pytest.mark.asyncio
    async def test_identity_resolved_on_ingest(self) -> None:
        db = MockDB()
        connector = _make_connector(_make_raw_events(2))
        await run_connector(db, connector, "audit")  # type: ignore[arg-type]

        for doc in db["events"].docs.values():
            assert doc["actor_id"] is not None
            assert doc["actor_id"].startswith("person:")

        assert len(db["identities"].docs) == 1
