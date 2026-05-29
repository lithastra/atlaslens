from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from atlaslens.api.deps import get_database
from atlaslens.api.main import app


def _mock_db_with_sync_state() -> MagicMock:
    sync_col = MagicMock()
    sync_col.find_one = AsyncMock(return_value=None)

    db = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    db.list_collection_names = AsyncMock(return_value=[])
    db.__getitem__ = MagicMock(return_value=sync_col)
    return db


@pytest.mark.asyncio
async def test_sync_status_returns_connectors() -> None:
    db = _mock_db_with_sync_state()
    app.dependency_overrides[get_database] = lambda: db
    from httpx import ASGITransport

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 6

    ids = [s["connector"] for s in data]
    assert "cloud:confluence:audit" in ids
    assert "cloud:bitbucket:audit" in ids
    assert "cloud:jira:activity" in ids
    assert "cloud:confluence:activity" in ids
    assert "cloud:jsm:activity" in ids
    assert "cloud:bitbucket:activity" in ids


@pytest.mark.asyncio
async def test_sync_status_shows_guard_gap() -> None:
    db = _mock_db_with_sync_state()
    app.dependency_overrides[get_database] = lambda: db
    from httpx import ASGITransport

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")

    app.dependency_overrides.clear()

    data = resp.json()
    bb = next(s for s in data if s["product"] == "bitbucket")
    assert "Guard" in (bb.get("note") or "")
