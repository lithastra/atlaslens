from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.api.main import app
from atlaslens.api.routes import sync as sync_module
from atlaslens.ingest.manager import manager


def _mock_db_with_sync_state() -> MagicMock:
    sync_col = MagicMock()
    sync_col.find_one = AsyncMock(return_value=None)

    db = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    db.list_collection_names = AsyncMock(return_value=[])
    db.__getitem__ = MagicMock(return_value=sync_col)
    return db


def _idle_snapshot() -> dict[str, Any]:
    return {
        "running": False,
        "cancelled": False,
        "started_at": None,
        "finished_at": None,
        "connectors": {},
    }


@pytest.mark.asyncio
async def test_sync_status_returns_connectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "snapshot", _idle_snapshot)
    db = _mock_db_with_sync_state()
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    conns = data["connectors"]
    assert len(conns) == 9  # 8 connectors + group sync

    ids = [s["connector"] for s in conns]
    for expected in [
        "cloud:jira:audit",
        "cloud:jsm:audit",
        "cloud:confluence:audit",
        "cloud:bitbucket:audit",
        "cloud:jira:activity",
        "cloud:confluence:activity",
        "cloud:jsm:activity",
        "cloud:bitbucket:activity",
        "cloud:atlassian-org:groups",
    ]:
        assert expected in ids
    # idle connectors with no sync_state derive state "idle"
    assert all(s["state"] == "idle" for s in conns)


@pytest.mark.asyncio
async def test_sync_status_shows_guard_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager, "snapshot", _idle_snapshot)
    db = _mock_db_with_sync_state()
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")
    app.dependency_overrides.clear()

    bb = next(
        s
        for s in resp.json()["connectors"]
        if s["connector"] == "cloud:bitbucket:audit"
    )
    assert "Guard" in (bb.get("note") or "")


@pytest.mark.asyncio
async def test_sync_status_reflects_live_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snap = {
        "running": True,
        "cancelled": False,
        "started_at": "2026-06-06T00:00:00+00:00",
        "finished_at": None,
        "connectors": {
            "cloud:jira:audit": {"state": "running", "count": None},
            "cloud:jsm:audit": {"state": "done", "count": 7},
        },
    }
    monkeypatch.setattr(manager, "snapshot", lambda: snap)
    db = _mock_db_with_sync_state()
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get("/sync-status")
    app.dependency_overrides.clear()

    data = resp.json()
    assert data["running"] is True
    by_id = {s["connector"]: s for s in data["connectors"]}
    assert by_id["cloud:jira:audit"]["state"] == "running"
    assert by_id["cloud:jsm:audit"]["state"] == "done"
    assert by_id["cloud:jsm:audit"]["count"] == 7


@pytest.mark.asyncio
async def test_trigger_sync_cancels_and_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = AsyncMock(return_value="started")
    monkeypatch.setattr(manager, "start", start)
    monkeypatch.setattr(sync_module, "get_db", lambda: MagicMock())
    app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.post("/sync")
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "started"}
    start.assert_awaited_once()
    # manual sync must pre-empt any in-flight sync
    assert start.await_args is not None
    assert start.await_args.kwargs["cancel_existing"] is True


@pytest.mark.asyncio
async def test_trigger_sync_requires_auth() -> None:
    app.dependency_overrides[get_database] = _mock_db_with_sync_state
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.post("/sync")
    app.dependency_overrides.clear()
    assert resp.status_code in (401, 403)
