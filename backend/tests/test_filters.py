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

    def sort(self, *a: Any, **kw: Any) -> "_AsyncIter":
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


# Two identities; only alice is a member of group "g1".
IDENTITIES = [
    {"_id": "person:1", "display_name": "Alice"},
    {"_id": "person:2", "display_name": "Bob"},
]


def _setup(db: _MockDB) -> None:
    db["users"].find_one = AsyncMock(
        return_value={
            "_id": "admin",
            "username": "admin",
            "password_hash": hash_password("secret123"),
            "created_at": datetime.now(UTC),
            "disabled": False,
        }
    )
    db["events"].distinct = AsyncMock(return_value=["login", "logout"])
    db["canonical_groups"].find = lambda *a, **kw: _AsyncIter(
        [{"_id": "g1", "name": "Engineering"}]
    )

    async def membership_distinct(
        field: str, query: dict[str, Any] | None = None
    ) -> list[str]:
        if field == "canonical_group_id":
            return ["g1"]
        # identity_id for a specific group
        if query and query.get("canonical_group_id") == "g1":
            return ["person:1"]
        return []

    db["group_membership"].distinct = AsyncMock(side_effect=membership_distinct)

    def identities_find(
        query: dict[str, Any], *a: Any, **kw: Any
    ) -> _AsyncIter:
        id_filter = query.get("_id")
        allowed = (
            id_filter.get("$in") if isinstance(id_filter, dict) else None
        )
        docs = (
            IDENTITIES
            if allowed is None
            else [d for d in IDENTITIES if d["_id"] in allowed]
        )
        return _AsyncIter(docs)

    db["identities"].find = identities_find


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token('admin')}"}


class TestFilters:
    def test_all_users_without_group(self) -> None:
        db = _MockDB()
        _setup(db)
        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/filters", headers=_auth())
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        names = [u["name"] for u in resp.json()["users"]]
        assert names == ["Alice", "Bob"]

    def test_group_narrows_user_list(self) -> None:
        db = _MockDB()
        _setup(db)
        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/filters?group=g1", headers=_auth())
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        users = resp.json()["users"]
        assert [u["id"] for u in users] == ["person:1"]
        assert users[0]["name"] == "Alice"
