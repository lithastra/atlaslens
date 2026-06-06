from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.api.main import app

_SUMMARY_DOC = {
    "total": [{"n": 3}],
    "by_product": [],
    "by_category": [],
    "by_severity": [],
    "unique_actors": [{"n": 1}],
}


class _AsyncIter:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def __aiter__(self) -> "_AsyncIter":
        self._i = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._i >= len(self._items):
            raise StopAsyncIteration
        v = self._items[self._i]
        self._i += 1
        return v


class _EventsCol:
    def __init__(self) -> None:
        self.captured: list[dict[str, Any]] | None = None

    def aggregate(self, pipeline: list[dict[str, Any]]) -> _AsyncIter:
        self.captured = pipeline
        return _AsyncIter([_SUMMARY_DOC])


class _MembersCol:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def find(self, *a: Any, **kw: Any) -> _AsyncIter:
        return _AsyncIter([{"identity_id": i} for i in self._ids])


class _DB:
    def __init__(self, events: _EventsCol, members: list[str]) -> None:
        self._events = events
        self._members = _MembersCol(members)

    def __getitem__(self, name: str) -> Any:
        if name == "events":
            return self._events
        if name == "group_membership":
            return self._members
        raise KeyError(name)


def _match_of(events: _EventsCol) -> dict[str, Any]:
    assert events.captured is not None
    match: dict[str, Any] = events.captured[0]["$match"]
    return match


async def _call(db: _DB, query: str) -> None:
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"username": "admin"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        resp = await c.get(f"/aggregations/summary{query}")
    app.dependency_overrides.clear()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_summary_applies_actor_filter() -> None:
    events = _EventsCol()
    await _call(_DB(events, []), "?actor=person:1")
    match = _match_of(events)
    assert {"actor_id": "person:1"} in match["$or"]
    assert {"actor_raw": "person:1"} in match["$or"]


@pytest.mark.asyncio
async def test_summary_applies_group_filter() -> None:
    events = _EventsCol()
    await _call(_DB(events, ["person:1", "person:2"]), "?group=g1")
    match = _match_of(events)
    assert match["actor_id"] == {"$in": ["person:1", "person:2"]}


@pytest.mark.asyncio
async def test_summary_no_filter_has_empty_match() -> None:
    events = _EventsCol()
    await _call(_DB(events, []), "")
    assert _match_of(events) == {}
