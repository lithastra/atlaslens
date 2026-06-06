import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.api.main import app
from atlaslens.api.routes import sync as sync_module


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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 8

    ids = [s["connector"] for s in data]
    assert "cloud:jira:audit" in ids
    assert "cloud:jsm:audit" in ids
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")

    app.dependency_overrides.clear()

    data = resp.json()
    bb = next(s for s in data if s["product"] == "bitbucket")
    assert "Guard" in (bb.get("note") or "")


@pytest.mark.asyncio
async def test_trigger_sync_starts_background_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = AsyncMock(return_value={"jira:audit": 0})
    monkeypatch.setattr(sync_module, "run_all", ran)
    monkeypatch.setattr(sync_module, "get_db", lambda: MagicMock())
    monkeypatch.setattr(sync_module, "_sync_running", False)
    app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.post("/sync")
    # let the background task run and clear the flag
    await asyncio.sleep(0.05)
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "started"}
    ran.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_sync_is_noop_when_already_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = AsyncMock()
    monkeypatch.setattr(sync_module, "run_all", ran)
    monkeypatch.setattr(sync_module, "_sync_running", True)
    app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.post("/sync")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "already_running"}
    ran.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_sync_requires_auth() -> None:
    # Override the DB so the auth dependency resolves to a 401 rather than
    # failing on an unconnected database.
    app.dependency_overrides[get_database] = _mock_db_with_sync_state
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.post("/sync")
    app.dependency_overrides.clear()
    assert resp.status_code in (401, 403)
