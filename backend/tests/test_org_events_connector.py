import httpx
import pytest

from atlaslens.connectors.cloud.org_events import OrgEventsConnector


def _stream_response(
    items: list[dict],  # type: ignore[type-arg]
    next_cursor: str | None = None,
) -> dict:  # type: ignore[type-arg]
    return {
        "data": items,
        "meta": {"next_cursor": next_cursor},
    }


def _event_item(
    event_id: str = "evt-1",
    action: str = "user_added_to_org",
    time: str = "2026-04-15T12:00:00Z",
) -> dict:  # type: ignore[type-arg]
    return {
        "id": event_id,
        "attributes": {
            "action": action,
            "time": time,
            "actor": {"id": "admin-1"},
            "target": {"id": "user-99", "name": "bob"},
            "context": {},
            "location": {"ip": "203.0.113.5"},
        },
    }


class TestOrgEventsConnector:
    @pytest.mark.asyncio
    async def test_fetch_single_page(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=_stream_response(
                    [_event_item("e1"), _event_item("e2")]
                ),
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = OrgEventsConnector("org-123", "key", client)
            events = await conn.fetch_audit(None)

        assert len(events) == 2
        assert events[0].source_id == "e1"

    @pytest.mark.asyncio
    async def test_cursor_pagination(self) -> None:
        call_count = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            cursor = req.url.params.get("cursor")
            if not cursor:
                return httpx.Response(
                    200,
                    json=_stream_response(
                        [_event_item("e1")],
                        next_cursor="page2",
                    ),
                )
            return httpx.Response(
                200,
                json=_stream_response([_event_item("e2")]),
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = OrgEventsConnector("org-123", "key", client)
            events = await conn.fetch_audit(None)

        assert len(events) == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_bearer_auth_header(self) -> None:
        captured_headers: list[dict] = []  # type: ignore[type-arg]

        def handler(req: httpx.Request) -> httpx.Response:
            captured_headers.append(dict(req.headers))
            return httpx.Response(
                200, json=_stream_response([])
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = OrgEventsConnector("org-123", "my-key", client)
            await conn.fetch_audit(None)

        assert "Bearer my-key" in captured_headers[0]["authorization"]

    @pytest.mark.asyncio
    async def test_fetch_activity_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = OrgEventsConnector("org-123", "key", client)
            events = await conn.fetch_activity(None)

        assert events == []
