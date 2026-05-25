from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from atlaslens.api.auth import create_access_token, hash_password
from atlaslens.api.deps import get_database
from atlaslens.api.main import app


class _AsyncIter:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items
        self._idx = 0

    def sort(self, *a: Any, **kw: Any) -> "_AsyncIter":
        return self

    def skip(self, *a: Any, **kw: Any) -> "_AsyncIter":
        return self

    def limit(self, *a: Any, **kw: Any) -> "_AsyncIter":
        return self

    def __aiter__(self) -> "_AsyncIter":
        self._idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _MockDB:
    def __init__(self) -> None:
        self._cols: dict[str, AsyncMock] = defaultdict(AsyncMock)

    def __getitem__(self, name: str) -> AsyncMock:
        return self._cols[name]


def _setup_user(db: _MockDB) -> None:
    db["users"].find_one = AsyncMock(
        return_value={
            "_id": "admin",
            "username": "admin",
            "password_hash": hash_password("secret123"),
            "created_at": datetime.now(UTC),
            "disabled": False,
        }
    )


def _auth_header() -> dict[str, str]:
    token = create_access_token("admin")
    return {"Authorization": f"Bearer {token}"}


class TestListEvents:
    def test_requires_auth(self) -> None:
        db = _MockDB()
        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/events")
        app.dependency_overrides.clear()
        assert resp.status_code in (401, 403)

    def test_returns_events(self) -> None:
        db = _MockDB()
        _setup_user(db)
        db["events"].count_documents = AsyncMock(return_value=1)

        event_doc = {
            "_id": "cloud:jira:1",
            "occurred_at": datetime(
                2026, 4, 20, tzinfo=UTC
            ),
            "product": "jira",
            "deployment": "cloud",
            "pipeline": "audit",
            "actor_raw": "u1",
            "operation": "permission_changed",
            "category": "security",
            "severity": "high",
            "object_type": "config",
            "object_ref": {"id": "x", "name": "y"},
        }
        db["events"].find = lambda *a, **kw: _AsyncIter(
            [event_doc]
        )

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/events", headers=_auth_header())
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "cloud:jira:1"


class TestGetEvent:
    def test_not_found(self) -> None:
        db = _MockDB()
        _setup_user(db)
        db["events"].find_one = AsyncMock(return_value=None)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/events/cloud:jira:999", headers=_auth_header()
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 404

    def test_returns_event(self) -> None:
        db = _MockDB()
        _setup_user(db)
        db["events"].find_one = AsyncMock(
            return_value={
                "_id": "cloud:jira:1",
                "occurred_at": datetime(
                    2026, 4, 20, tzinfo=UTC
                ),
                "product": "jira",
                "deployment": "cloud",
                "pipeline": "audit",
                "actor_raw": "u1",
                "operation": "permission_changed",
                "category": "security",
                "severity": "high",
                "object_type": "config",
                "object_ref": {"id": "x", "name": "y"},
                "raw": {"original": "data"},
            }
        )

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/events/cloud:jira:1", headers=_auth_header()
        )
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["id"] == "cloud:jira:1"
        assert "raw" in resp.json()
